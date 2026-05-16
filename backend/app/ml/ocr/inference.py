"""TrOCR-based text extraction for checklist images."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import torch
import numpy as np
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

from backend.app.ml.preprocessing import ImageRegion


@dataclass
class OCRExtractionResult:
    text: str
    confidence: float
    region_type: str  # 'header', 'activity', 'numeric', 'time'


class TrOCRExtractor:
    """TrOCR-based text extraction engine for handwritten checklist scans."""

    def __init__(self, model_name: str = "microsoft/trocr-base-printed"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = TrOCRProcessor.from_pretrained(model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def extract_text(self, image: np.ndarray) -> Tuple[str, float]:
        """Extract text from an image region using TrOCR.
        
        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        # Convert numpy array to PIL Image if needed
        if isinstance(image, np.ndarray):
            if image.dtype == np.uint8 and len(image.shape) == 3:
                image = Image.fromarray(image, mode="BGR").convert("RGB")
            elif image.dtype == np.uint8 and len(image.shape) == 2:
                image = Image.fromarray(image, mode="L").convert("RGB")
            else:
                image = Image.fromarray((image * 255).astype(np.uint8)).convert("RGB")

        # Prepare image for model
        pixel_values = self.processor(image, return_tensors="pt").pixel_values.to(self.device)

        # Generate text with confidence
        with torch.no_grad():
            generated_ids = self.model.generate(pixel_values, max_length=128, output_scores=True, return_dict_in_generate=True)

        # Decode text
        generated_text = self.processor.batch_decode(generated_ids.sequences, skip_special_tokens=True)[0].strip()

        # Calculate confidence from sequence scores
        if hasattr(generated_ids, 'sequences_scores') and len(generated_ids.sequences_scores) > 0:
            confidence = float(generated_ids.sequences_scores[0].cpu().numpy())
            confidence = np.exp(confidence) / (1 + np.exp(confidence))
        else:
            confidence = 0.7

        return generated_text, float(confidence)

    def process_regions(self, regions: List[ImageRegion]) -> Dict[Tuple[int, int], OCRExtractionResult]:
        """Process a list of segmented regions and extract text from each."""
        results = {}
        for region in regions:
            text, confidence = self.extract_text(region.image)
            region_key = (region.row_index, region.col_index)
            results[region_key] = OCRExtractionResult(
                text=text,
                confidence=confidence,
                region_type=self._infer_region_type(text),
            )
        return results

    @staticmethod
    def _infer_region_type(text: str) -> str:
        """Infer the type of region based on extracted text."""
        text_lower = text.lower().replace(" ", "")

        # Check for time pattern (HH:MM)
        if text.count(":") >= 1 or any(c.isdigit() for c in text if len(text) < 10):
            return "time"

        # Check for numeric code
        if text.isdigit() or (len(text) < 5 and text.replace("-", "").replace(".", "").isdigit()):
            return "numeric"

        # Check for header-like text (name, location)
        if len(text) > 3 and any(c.isalpha() for c in text):
            return "text"

        return "text"


def normalize_time_field(text: str) -> Optional[str]:
    """Normalize extracted time text to HH:MM format."""
    text = text.strip().replace(" ", "").upper()

    # Already in correct format
    if len(text) == 5 and text[2] == ":":
        try:
            h, m = map(int, text.split(":"))
            if 0 <= h < 24 and 0 <= m < 60:
                return f"{h:02d}:{m:02d}"
        except ValueError:
            pass

    # Extract digits and colons
    digits_and_colons = "".join(c for c in text if c.isdigit() or c == ":")
    parts = digits_and_colons.split(":")

    if len(parts) >= 2:
        try:
            hour = int(parts[0][-2:]) if len(parts[0]) > 0 else 0
            minute = int(parts[1][:2]) if len(parts[1]) > 0 else 0
            if 0 <= hour < 24 and 0 <= minute < 60:
                return f"{hour:02d}:{minute:02d}"
        except ValueError:
            pass

    return None


def normalize_numeric_field(text: str) -> Optional[str]:
    """Normalize extracted numeric text (activity codes, loads, etc.)."""
    text = text.strip().replace(" ", "").upper()
    digits = "".join(c for c in text if c.isdigit() or c == ".")
    if digits:
        return digits[:10]
    return None


def normalize_text_field(text: str) -> Optional[str]:
    """Normalize extracted text field (names, locations, etc.)."""
    text = text.strip()
    if len(text) >= 2:
        return text
    return None


def aggregate_row_text(region_results: Dict[Tuple[int, int], OCRExtractionResult], row_index: int) -> Dict[str, str]:
    """Aggregate extracted text from a row of table cells."""
    row_text = {}
    cols = sorted([col for (r, col) in region_results.keys() if r == row_index])

    for col_idx, col in enumerate(cols):
        region_key = (row_index, col)
        if region_key in region_results:
            result = region_results[region_key]
            row_text[f"col_{col_idx}"] = result.text
    return row_text
