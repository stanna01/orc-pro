"""OCR extraction service using TrOCR model."""

import logging
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
from typing import List, Dict, Tuple, Optional, Union
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

logger = logging.getLogger(__name__)


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


class SimulatedOCRExtractor:
    """Development-only stub that returns clearly-marked synthetic OCR results.

    MUST NOT be used in production — no real image content is ever read.
    All output carries ``simulated=True`` and text is the literal string
    ``SIMULATED_OCR``. Any downstream code that accepts this output will
    produce meaningless analytics.

    Use ``initialize_ocr_extractor()`` as the factory; it falls back here
    automatically in non-production environments when TrOCR is unavailable.
    """

    simulated = True

    def extract_text(self, image, confidence: bool = False) -> Dict:
        """Return a low-confidence synthetic result. Never reads actual pixels."""
        is_blank = False
        if np is not None:
            try:
                arr = image if isinstance(image, np.ndarray) else np.array(image)
                is_blank = arr.size == 0 or (arr.mean() < 2 and arr.std() < 2)
            except Exception:
                pass
        elif PIL_AVAILABLE and Image is not None and hasattr(image, "convert"):
            try:
                extrema = image.convert("L").getextrema()
                is_blank = extrema == (0, 0) or (extrema[0] == extrema[1] and extrema[0] >= 250)
            except Exception:
                pass

        if is_blank:
            return {
                "text": "",
                "confidence": None,
                "tokens": [],
                "classification": "unreadable",
                "needs_review": False,
                "simulated": True,
                "attempts": [],
            }
        return {
            "text": "SIMULATED_OCR",
            "confidence": 0.35,
            "tokens": ["SIMULATED_OCR"],
            "classification": "low",
            "needs_review": True,
            "simulated": True,
            "attempts": [{"attempt": "simulated", "text": "SIMULATED_OCR", "confidence": 0.35}],
        }

    def extract_text_from_regions(
        self,
        image,
        regions: List[Tuple[int, int, int, int]],
    ) -> List[Dict]:
        """Return synthetic results for each bounding-box region."""
        results = []
        for i, (x, y, w, h) in enumerate(regions):
            if h < 20 or w < 20:
                continue
            try:
                region_img = image[y:y + h, x:x + w] if np is not None else image
            except Exception:
                region_img = image
            result = self.extract_text(region_img)
            result["region_index"] = i
            result["bbox"] = (int(x), int(y), int(w), int(h))
            results.append(result)
        return results


class TrOCRExtractor:
    """Handwritten text extraction using the real TrOCR model.

    Raises ``RuntimeError`` at construction if torch/transformers are missing
    or if the model weights cannot be loaded.  Never falls back silently.

    Use ``initialize_ocr_extractor()`` as the factory — it decides whether to
    return a ``TrOCRExtractor`` or a ``SimulatedOCRExtractor`` based on
    availability and the ``fail_on_missing`` flag.
    """

    simulated = False

    def __init__(self, model_name: str = "microsoft/trocr-large-handwritten"):
        if not TORCH_AVAILABLE or not TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "torch and transformers are required for TrOCRExtractor. "
                "Install them or use SimulatedOCRExtractor for development."
            )
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Loading TrOCR model ({model_name}) on {self.device}...")
            self.processor = TrOCRProcessor.from_pretrained(model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            print("TrOCR model loaded successfully")
        except Exception as e:
            raise RuntimeError(f"TrOCR model could not be loaded: {e}") from e

    def extract_text(self, image: Union["np.ndarray", "Image.Image"], confidence: bool = False) -> Dict:
        """Extract text from image using TrOCR.

        Args:
            image: Input image (numpy array or PIL Image)
            confidence: Unused; confidence is always computed when possible

        Returns:
            Dict with keys: text, confidence, tokens, classification,
            needs_review, attempts
        """
        # Convert numpy array to PIL Image if needed
        if np is not None and isinstance(image, np.ndarray):
            if len(image.shape) == 2:
                pil_img = Image.fromarray(image, mode='L')
            else:
                pil_img = Image.fromarray(image)
        else:
            pil_img = image

        def _run_model(img) -> Dict:
            try:
                pixel_values = self.processor(images=img, return_tensors="pt").pixel_values
                pixel_values = pixel_values.to(self.device)

                with torch.no_grad():
                    gen_out = self.model.generate(pixel_values, return_dict_in_generate=True, output_scores=True)

                generated_ids = gen_out.sequences
                text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

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

        attempts = []

        def attempt(name: str, img) -> Dict:
            out = _run_model(img)
            attempts.append({"attempt": name, "text": out.get("text", ""), "confidence": out.get("confidence"), "error": out.get("error")})
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
                if retry.get("confidence") is not None and (primary.get("confidence") is None or retry["confidence"] > primary.get("confidence")):
                    primary = retry
            else:
                attempts.append({"attempt": "autocontrast_skipped", "reason": "PIL unavailable"})

        # 3) If still fails, try aggressive preprocessing
        conf_val = primary.get("confidence")
        if not primary.get("text") or conf_val is None or (isinstance(conf_val, float) and conf_val < CONF_LOW):
            if PIL_AVAILABLE and hasattr(pil_img, "convert") and ImageOps is not None and ImageFilter is not None:
                try:
                    ag = pil_img.convert("L")
                    ag = ag.resize((int(ag.width * 1.5), int(ag.height * 1.5)), Image.BICUBIC)
                    ag = ImageOps.autocontrast(ag)
                    ag = ag.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
                    ag = ag.point(lambda p: 255 if p > 128 else 0)
                    retry2 = attempt("aggressive_resize_binarize", ag)
                    if retry2.get("confidence") is not None and (primary.get("confidence") is None or retry2["confidence"] > primary.get("confidence")):
                        primary = retry2
                except Exception as e:
                    attempts.append({"attempt": "aggressive_preprocess_error", "error": str(e)})
            else:
                attempts.append({"attempt": "aggressive_preprocess_skipped", "reason": "PIL unavailable"})

        final_conf = primary.get("confidence")
        classification = _classify_confidence(final_conf)
        needs_review = not primary.get("text") or final_conf is None or (isinstance(final_conf, float) and final_conf < CONF_LOW)

        return {
            "text": primary.get("text", ""),
            "confidence": final_conf,
            "tokens": primary.get("tokens", []),
            "classification": classification,
            "needs_review": needs_review,
            "attempts": attempts,
        }

    def extract_text_from_regions(
        self,
        image: "np.ndarray",
        regions: List[Tuple[int, int, int, int]],
    ) -> List[Dict]:
        """Extract text from multiple bounding-box regions in an image.

        Args:
            image: Source image (numpy array)
            regions: List of (x, y, w, h) bounding boxes

        Returns:
            List of extraction result dicts, one per valid region
        """
        results = []

        for i, (x, y, w, h) in enumerate(regions):
            region_img = image[y:y + h, x:x + w]

            if region_img.shape[0] < 20 or region_img.shape[1] < 20:
                continue

            try:
                extraction = self.extract_text(region_img)
            except Exception as e:
                extraction = {
                    "text": "",
                    "confidence": None,
                    "tokens": [],
                    "classification": "unreadable",
                    "needs_review": True,
                    "attempts": [{"attempt": "exception", "error": str(e)}],
                }

            extraction["region_index"] = i
            extraction["bbox"] = (int(x), int(y), int(w), int(h))
            if "classification" not in extraction:
                extraction["classification"] = _classify_confidence(extraction.get("confidence"))

            # Re-segment into horizontal slices when unreadable
            if extraction.get("needs_review") or (not extraction.get("text") and extraction.get("confidence") is None):
                try:
                    h_slice = max(20, int(h / 2))
                    combined_texts = []
                    combined_confidences = []
                    slices = []
                    for s in range(2):
                        yy = y + s * h_slice
                        hh = h_slice if (yy + h_slice) <= (y + h) else (y + h - yy)
                        if hh <= 0:
                            continue
                        sub_res = self.extract_text(image[yy:yy + hh, x:x + w])
                        slices.append(sub_res)
                        if sub_res.get("text"):
                            combined_texts.append(sub_res["text"])
                        if isinstance(sub_res.get("confidence"), float):
                            combined_confidences.append(sub_res["confidence"])

                    if combined_texts:
                        extraction["text"] = " \n ".join(combined_texts)
                        extraction["confidence"] = max(combined_confidences) if combined_confidences else None
                        extraction["tokens"] = extraction["text"].split()
                        extraction["classification"] = _classify_confidence(extraction.get("confidence"))
                        extraction["needs_review"] = not (extraction.get("confidence") and extraction["confidence"] >= CONF_LOW)
                        extraction["re_segments"] = slices
                except Exception as e:
                    extraction.setdefault("attempts", []).append({"attempt": "resegmentation_error", "error": str(e)})

            results.append(extraction)

        return results


def initialize_ocr_extractor(fail_on_missing: bool = False) -> Union[TrOCRExtractor, SimulatedOCRExtractor]:
    """Factory that returns a real or simulated OCR extractor.

    Args:
        fail_on_missing: When True, raises RuntimeError if TrOCR cannot load.
                         Set this to True in production environments.
                         When False (default), falls back to SimulatedOCRExtractor
                         with a logged warning.

    Returns:
        TrOCRExtractor if model loads successfully; SimulatedOCRExtractor otherwise.
    """
    try:
        return TrOCRExtractor()
    except RuntimeError as exc:
        if fail_on_missing:
            raise
        logger.warning(
            "TrOCR model unavailable (%s). Falling back to SimulatedOCRExtractor — "
            "ALL OCR outputs will be synthetic. DO NOT use these results in production.",
            exc,
        )
        return SimulatedOCRExtractor()


if __name__ == "__main__":
    import sys
    from pdf_processor import extract_pages_from_pdf, preprocess_image, detect_table_regions

    if len(sys.argv) < 2:
        print("Usage: python ocr_extractor.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = extract_pages_from_pdf(pdf_path)
    print(f"Extracted {len(pages)} pages from PDF")

    ocr = initialize_ocr_extractor()
    page = pages[0]
    preprocessed = preprocess_image(page)
    regions = detect_table_regions(preprocessed)

    print(f"\nProcessing page 1 ({len(regions)} regions)...")
    results = ocr.extract_text_from_regions(preprocessed, regions)

    for result in results[:5]:
        print(f"Region {result['region_index']}: {result['text'][:100]}")
