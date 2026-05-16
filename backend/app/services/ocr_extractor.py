"""OCR extraction service using TrOCR model."""

import math
try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False
try:
    import numpy as np
except Exception:
    np = None
from typing import List, Dict, Tuple, Optional
try:
    from PIL import Image, ImageOps, ImageFilter
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageOps = None
    ImageFilter = None
    PIL_AVAILABLE = False

try:
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    TRANSFORMERS_AVAILABLE = True
except Exception:
    TrOCRProcessor = None
    VisionEncoderDecoderModel = None
    TRANSFORMERS_AVAILABLE = False

# Confidence thresholds
CONF_HIGH = 0.85
CONF_MED = 0.70
CONF_LOW = 0.5  # below this triggers fallback


def _classify_confidence(conf: float) -> str:
    if conf is None:
        return "unreadable"
    if conf >= CONF_HIGH:
        return "high"
    if conf >= CONF_MED:
        return "medium"
    if conf >= 0.0:
        return "low"
    return "unreadable"


class TrOCRExtractor:
    """Handwritten text extraction using TrOCR model."""
    
    def __init__(self, model_name: str = "microsoft/trocr-large-handwritten"):
        """Initialize TrOCR model.
        
        Args:
            model_name: HuggingFace model identifier
        """
        self.device = None
        self.processor = None
        self.model = None
        self.simulated = False

        if TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE:
            try:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"Loading TrOCR model ({model_name}) on {self.device}...")
                self.processor = TrOCRProcessor.from_pretrained(model_name)
                self.model = VisionEncoderDecoderModel.from_pretrained(model_name).to(self.device)
                self.model.eval()
                print("TrOCR model loaded successfully")
            except Exception as e:
                # Fall back to simulated extractor if model loading fails
                print(f"Warning: could not load TrOCR model ({e}); using simulated extractor")
                self.simulated = True
        else:
            print("Torch/transformers not available; using simulated OCR extractor")
            self.simulated = True
    
    def extract_text(self, image: np.ndarray, confidence: bool = False) -> Dict:
        """Extract text from image using TrOCR.
        
        Args:
            image: Input image (numpy array or PIL Image)
            confidence: Include confidence scores (slower)
            
        Returns:
            Dictionary with:
            - text: Extracted text
            - confidence: Average confidence (if confidence=True)
            - tokens: List of tokens extracted
        """
        # Convert numpy array to PIL Image if needed (guard when numpy unavailable)
        if np is not None and isinstance(image, np.ndarray):
            if len(image.shape) == 2:  # Grayscale
                pil_img = Image.fromarray(image, mode='L')
            else:
                pil_img = Image.fromarray(image)
        else:
            pil_img = image

        def _run_model(img: Image.Image) -> Dict:
            # If model not available (no torch/transformers or simulated), return lightweight simulated result
            if getattr(self, "simulated", False):
                try:
                    # simple heuristic: if image is nearly blank, return empty; otherwise return low-confidence placeholder
                    if np is not None:
                        arr = np.array(img.convert("L")) if hasattr(img, "convert") else np.array(img)
                        is_blank = (arr.size == 0) or (arr.mean() < 2 and arr.std() < 2)
                    else:
                        # Fallback using PIL: check bbox/ extrema
                        try:
                            if hasattr(img, "convert"):
                                pil_g = img.convert("L")
                                extrema = pil_g.getextrema()
                                is_blank = (extrema == (0, 0)) or (extrema[0] == extrema[1] and extrema[0] >= 250)
                            else:
                                is_blank = True
                        except Exception:
                            is_blank = True

                    if is_blank:
                        return {"text": "", "confidence": None, "tokens": []}
                    else:
                        return {"text": "SIMULATED_OCR", "confidence": 0.35, "tokens": ["SIMULATED_OCR"]}
                except Exception:
                    return {"text": "", "confidence": None, "tokens": [], "error": "simulated_extraction_failed"}

            try:
                pixel_values = self.processor(images=img, return_tensors="pt").pixel_values
                pixel_values = pixel_values.to(self.device)

                # Generate text sequence
                with torch.no_grad():
                    gen_out = self.model.generate(pixel_values, return_dict_in_generate=True, output_scores=True)

                generated_ids = gen_out.sequences
                text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

                # Compute confidence via teacher-forcing loss on generated tokens
                try:
                    labels = self.processor.tokenizer(text, return_tensors="pt").input_ids.to(self.device)
                    with torch.no_grad():
                        loss_out = self.model(pixel_values=pixel_values, labels=labels)
                    loss = loss_out.loss.item() if hasattr(loss_out, "loss") else None
                    conf = float(math.exp(-loss)) if loss is not None else None
                    if conf is not None:
                        conf = max(0.0, min(1.0, conf))
                except Exception:
                    conf = None

                return {"text": text, "confidence": conf, "tokens": text.split()}
            except Exception as e:
                return {"text": "", "confidence": None, "tokens": [], "error": str(e)}

        # Track attempts for auditability
        attempts = []

        # Helper to run with metadata
        def attempt(name: str, img: Image.Image):
            out = _run_model(img)
            out_meta = {"attempt": name, "text": out.get("text", ""), "confidence": out.get("confidence"), "error": out.get("error")}
            attempts.append(out_meta)
            return out

        # 1) Primary attempt (original image)
        primary = attempt("original", pil_img)

        # 2) If empty or very low confidence, try mild preprocessing
        conf_val = primary.get("confidence")
        if not primary.get("text") or conf_val is None or (isinstance(conf_val, float) and conf_val < CONF_LOW):
            if PIL_AVAILABLE and hasattr(pil_img, "convert") and ImageOps is not None and ImageFilter is not None:
                alt = pil_img.convert("L")
                alt = ImageOps.autocontrast(alt)
                alt = alt.filter(ImageFilter.MedianFilter(size=3))
                retry = attempt("autocontrast_median", alt)
                if retry.get("confidence") is not None and (primary.get("confidence") is None or (retry["confidence"] > primary.get("confidence"))):
                    primary = retry
            else:
                # Cannot run PIL-based preprocessing in this environment
                attempts.append({"attempt": "autocontrast_skipped", "reason": "PIL unavailable"})

        # 3) If still fails, try aggressive preprocessing: resize, binarize, sharpen
        conf_val = primary.get("confidence")
        if not primary.get("text") or conf_val is None or (isinstance(conf_val, float) and conf_val < CONF_LOW):
            if PIL_AVAILABLE and hasattr(pil_img, "convert") and ImageOps is not None and ImageFilter is not None:
                try:
                    ag = pil_img.convert("L")
                    # upscale to help recognition
                    ag = ag.resize((int(ag.width * 1.5), int(ag.height * 1.5)), Image.BICUBIC)
                    ag = ImageOps.autocontrast(ag)
                    ag = ag.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
                    # simple binarization
                    ag = ag.point(lambda p: 255 if p > 128 else 0)
                    retry2 = attempt("aggressive_resize_binarize", ag)
                    if retry2.get("confidence") is not None and (primary.get("confidence") is None or (retry2["confidence"] > primary.get("confidence"))):
                        primary = retry2
                except Exception as e:
                    attempts.append({"attempt": "aggressive_preprocess_error", "error": str(e)})
            else:
                attempts.append({"attempt": "aggressive_preprocess_skipped", "reason": "PIL unavailable"})

        # 4) If still empty/low, mark as needs_review but return partial
        final_conf = primary.get("confidence")
        classification = _classify_confidence(final_conf)

        needs_review = False
        if (not primary.get("text")) or (final_conf is None) or (isinstance(final_conf, float) and final_conf < CONF_LOW):
            needs_review = True

        result = {
            "text": primary.get("text", ""),
            "confidence": final_conf,
            "tokens": primary.get("tokens", []),
            "classification": classification,
            "needs_review": needs_review,
            "attempts": attempts,
        }

        return result
    
    def extract_text_from_regions(
        self,
        image: np.ndarray,
        regions: List[Tuple[int, int, int, int]]
    ) -> List[Dict]:
        """Extract text from multiple regions in image.
        
        Args:
            image: Source image
            regions: List of (x, y, w, h) bounding boxes
            
        Returns:
            List of extraction results for each region
        """
        results = []
        
        for i, (x, y, w, h) in enumerate(regions):
            # Extract region
            region_img = image[y:y+h, x:x+w]
            
            # Skip very small regions
            if region_img.shape[0] < 20 or region_img.shape[1] < 20:
                continue
            
            # Extract text with robust failure handling
            try:
                extraction = self.extract_text(region_img)
            except Exception as e:
                extraction = {"text": "", "confidence": None, "tokens": [], "classification": "unreadable", "needs_review": True, "attempts": [{"attempt": "exception", "error": str(e)}]}

            extraction["region_index"] = i
            extraction["bbox"] = (int(x), int(y), int(w), int(h))
            # Ensure classification field present
            if "classification" not in extraction:
                extraction["classification"] = _classify_confidence(extraction.get("confidence"))

            # If unreadable or needs review, try re-segmentation into horizontal slices
            if extraction.get("needs_review") or (not extraction.get("text") and extraction.get("confidence") is None):
                slices = []
                try:
                    h_slice = max(20, int(h / 2))
                    combined_texts = []
                    combined_confidences = []
                    for s in range(2):
                        yy = y + s * h_slice
                        hh = h_slice if (yy + h_slice) <= (y + h) else (y + h - yy)
                        if hh <= 0:
                            continue
                        sub_img = image[yy:yy+hh, x:x+w]
                        sub_res = self.extract_text(sub_img)
                        slices.append(sub_res)
                        if sub_res.get("text"):
                            combined_texts.append(sub_res.get("text"))
                        if isinstance(sub_res.get("confidence"), float):
                            combined_confidences.append(sub_res.get("confidence"))

                    if combined_texts:
                        extraction["text"] = " \n ".join(combined_texts)
                        extraction["confidence"] = max(combined_confidences) if combined_confidences else None
                        extraction["tokens"] = extraction["text"].split()
                        extraction["classification"] = _classify_confidence(extraction.get("confidence"))
                        extraction["needs_review"] = False if extraction.get("confidence") and extraction.get("confidence") >= CONF_LOW else True
                        extraction["re_segments"] = slices
                except Exception as e:
                    extraction.setdefault("attempts", []).append({"attempt": "resegmentation_error", "error": str(e)})

            results.append(extraction)
        
        return results


def initialize_ocr_extractor() -> TrOCRExtractor:
    """Initialize and return TrOCR extractor (singleton pattern).
    
    Returns:
        TrOCRExtractor instance
    """
    return TrOCRExtractor()


if __name__ == "__main__":
    import sys
    from pdf_processor import extract_pages_from_pdf, preprocess_image, detect_table_regions
    
    if len(sys.argv) < 2:
        print("Usage: python ocr_extractor.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Extract pages
    pages = extract_pages_from_pdf(pdf_path)
    print(f"Extracted {len(pages)} pages from PDF")
    
    # Initialize OCR
    ocr = initialize_ocr_extractor()
    
    # Process first page
    page = pages[0]
    preprocessed = preprocess_image(page)
    regions = detect_table_regions(preprocessed)
    
    print(f"\nProcessing page 1 ({len(regions)} regions)...")
    results = ocr.extract_text_from_regions(preprocessed, regions)
    
    for result in results[:5]:  # Show first 5
        print(f"Region {result['region_index']}: {result['text'][:100]}")
