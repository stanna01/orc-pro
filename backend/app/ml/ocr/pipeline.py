"""OCR and table extraction for handwritten mining checklists."""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from backend.app.models.schemas import OCRField, OCRHeader, OCRActivityRow, OCROutput
from backend.app.ml.postprocessing import postprocess_ocr_output


PAGE1_FIELD_PATTERNS = {
    "machine_number": r"machine\s*number\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(operator|mine\s*number|permit|date|shift)\b|$)",
    "operator_name": r"operator\s*name\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(machine\s*number|mine\s*number|permit|date|shift)\b|$)",
    "mine_number": r"mine\s*number\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(machine\s*number|operator|permit|date|shift)\b|$)",
    "permit_number": r"permit\s*number\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(machine\s*number|operator|mine\s*number|date|shift)\b|$)",
    "date": r"date\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(machine\s*number|operator|mine\s*number|permit|shift)\b|$)",
    "shift": r"shift\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(machine\s*number|operator|mine\s*number|permit|date)\b|$)",
    "start_engine_hours": r"start\s*engine\s*hours\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(end\s*engine\s*hours|start\s*transmission\s*hours|end\s*transmission\s*hours)\b|$)",
    "end_engine_hours": r"end\s*engine\s*hours\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(start\s*transmission\s*hours|end\s*transmission\s*hours)\b|$)",
    "start_transmission_hours": r"start\s*transmission\s*hours\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*(end\s*transmission\s*hours)\b|$)",
    "end_transmission_hours": r"end\s*transmission\s*hours\s*[:\-]?\s*(?P<value>[^\n\r]+?)(?=\s*$)",
}

EXPECTED_ACTIVITY_COLUMNS = [
    "activity_code",
    "from_time",
    "to_time",
    "workplace",
    "ore_waste",
    "loads",
    "remarks",
]

BREAKDOWN_KEYWORDS = [
    r"hydraulic",
    r"fault",
    r"breakdown",
    r"stuck",
    r"repair",
    r"engine\s*failure",
    r"trouble",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def extract_page1_fields(raw_text: str) -> Dict[str, Optional[str]]:
    content = raw_text.replace("\r", "\n")
    result = {}
    for field_name, pattern in PAGE1_FIELD_PATTERNS.items():
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            value = normalize_text(match.group("value"))
            result[field_name] = value
        else:
            result[field_name] = None
    return result


def split_activity_rows(raw_text: str) -> List[str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    header_index = None
    for index, line in enumerate(lines):
        lower = line.lower()
        if all(col in lower for col in ["activity", "from", "to", "workplace", "ore", "loads"]):
            header_index = index
            break
    if header_index is None:
        return []

    rows: List[str] = []
    for line in lines[header_index + 1 :]:
        if re.search(r"machine\s*number|operator|permit|date|shift|start\s*engine", line, flags=re.IGNORECASE):
            break
        if line:
            rows.append(line)
    return rows


def parse_activity_row(line: str) -> Dict[str, Optional[str]]:
    line = re.sub(r"\s{2,}", "\t", line)
    parts = [part.strip() for part in re.split(r"\t|\s{2,}", line) if part.strip()]

    if len(parts) >= len(EXPECTED_ACTIVITY_COLUMNS):
        values = parts[: len(EXPECTED_ACTIVITY_COLUMNS) - 1]
        remarks = " ".join(parts[len(EXPECTED_ACTIVITY_COLUMNS) - 1 :])
        values.append(remarks)
    else:
        values = parts + [None] * (len(EXPECTED_ACTIVITY_COLUMNS) - len(parts))

    row = {
        "activity_code_raw": values[0] if values[0] else None,
        "from_time_raw": values[1] if len(values) > 1 else None,
        "to_time_raw": values[2] if len(values) > 2 else None,
        "workplace_raw": values[3] if len(values) > 3 else None,
        "ore_waste_raw": values[4] if len(values) > 4 else None,
        "loads_raw": values[5] if len(values) > 5 else None,
        "remarks_raw": values[6] if len(values) > 6 else None,
    }
    return {k: normalize_text(v) if v else None for k, v in row.items()}


def extract_activity_entries(raw_text: str) -> List[Dict[str, Optional[str]]]:
    rows = split_activity_rows(raw_text)
    return [parse_activity_row(row) for row in rows]


def guess_shift(raw_text: str) -> Optional[str]:
    lower = raw_text.lower()
    if "night" in lower:
        return "night"
    if "day" in lower:
        return "day"
    return None


def is_breakdown(activity_code: Optional[str], remarks: Optional[str]) -> bool:
    if activity_code:
        normalized = re.sub(r"\D", "", activity_code)
        if normalized.startswith("3") and len(normalized) >= 3:
            return True
    if remarks:
        lower = remarks.lower()
        return any(re.search(keyword, lower) for keyword in BREAKDOWN_KEYWORDS)
    return False


def prepare_image_for_ocr(image_path: str) -> List[ImageRegion]:
    """Preprocess a checklist image and return segmented table regions for OCR."""
    return preprocess_checklist_image(image_path)


def extract_checklist_ocr(raw_text: str, document_id: str) -> OCROutput:
    """Extract OCR data from raw text and return standardized OCROutput.
    
    This is the legacy text-based extraction. For image-based extraction,
    use extract_from_image() instead.
    """
    # Extract header fields
    page1 = extract_page1_fields(raw_text)

    # Extract activity entries
    activity_entries = extract_activity_entries(raw_text)

    # Build header with OCR fields
    header = OCRHeader(
        machine_id=OCRField(value=page1.get("machine_number"), confidence=0.9),
        operator_name=OCRField(value=page1.get("operator_name"), confidence=0.85),
        date=OCRField(value=page1.get("date"), confidence=0.95),
        shift=OCRField(value=page1.get("shift") or guess_shift(raw_text) or "day", confidence=0.8),
        engine_hours_start=OCRField(value=page1.get("start_engine_hours"), confidence=0.9),
        engine_hours_end=OCRField(value=page1.get("end_engine_hours"), confidence=0.9)
    )

    # Build activity rows
    activities = []
    for idx, entry in enumerate(activity_entries):
        activities.append(OCRActivityRow(
            row_index=idx,
            activity_code=OCRField(value=entry.get("activity_code_raw"), confidence=0.8),
            from_time=OCRField(value=entry.get("from_time_raw"), confidence=0.75),
            to_time=OCRField(value=entry.get("to_time_raw"), confidence=0.75),
            location=OCRField(value=entry.get("workplace_raw"), confidence=0.7),
            loads=OCRField(value=entry.get("loads_raw"), confidence=0.8),
            remarks=OCRField(value=entry.get("remarks_raw"), confidence=0.6)
        ))

    # Calculate total confidence
    total_confidence = 0.0
    field_count = 0
    for field in [header.machine_id, header.operator_name, header.date, header.shift,
                  header.engine_hours_start, header.engine_hours_end]:
        if field.value is not None:
            total_confidence += field.confidence
            field_count += 1
    for activity in activities:
        for field in [activity.activity_code, activity.from_time, activity.to_time,
                      activity.location, activity.loads, activity.remarks]:
            if field.value is not None:
                total_confidence += field.confidence
                field_count += 1
    avg_confidence = total_confidence / field_count if field_count > 0 else 0.0

    # Create raw OCR output
    raw_output = OCROutput(
        document_id=document_id,
        header=header,
        activities=activities,
        processing_metadata={
            "ocr_engine": "regex_extraction",
            "processing_time_seconds": 0.1,
            "total_confidence": round(avg_confidence, 3),
            "extracted_fields_count": field_count
        }
    )

    # Apply post-processing corrections
    processed_output = postprocess_ocr_output(raw_output)

    return processed_output


def extract_from_image(image_path: Union[str, Path], document_id: str) -> OCROutput:
    """Extract OCR data from a checklist image using TrOCR neural network.
    
    Processes the image through preprocessing and TrOCR inference,
    returning a structured OCROutput with confidence scores.
    """
    start_time = time.time()
    image_path = Path(image_path)

    # Preprocess image to get segmented regions
    regions = preprocess_checklist_image(image_path)
    if not regions:
        raise ValueError(f"No table structure detected in image: {image_path}")

    # Initialize TrOCR extractor
    extractor = TrOCRExtractor()

    # Process regions with TrOCR
    region_results = extractor.process_regions(regions)

    # Organize results by row and column
    rows_by_index = {}
    for (row_idx, col_idx), result in region_results.items():
        if row_idx not in rows_by_index:
            rows_by_index[row_idx] = {}
        rows_by_index[row_idx][col_idx] = result

    # Extract header (typically first row)
    header_row = rows_by_index.get(0, {})
    header = _build_header_from_regions(header_row)

    # Extract activity rows (remaining rows)
    activities = []
    for row_idx in sorted(rows_by_index.keys()):
        if row_idx == 0:
            continue  # Skip header row
        activity = _build_activity_from_row(row_idx, rows_by_index[row_idx])
        if activity:
            activities.append(activity)

    # Calculate total confidence
    total_confidence = _calculate_total_confidence(header, activities)
    processing_time = time.time() - start_time

    # Create raw OCR output
    raw_output = OCROutput(
        document_id=document_id,
        header=header,
        activities=activities,
        processing_metadata={
            "ocr_engine": "TrOCR",
            "processing_time_seconds": round(processing_time, 2),
            "total_confidence": round(total_confidence, 3),
            "extracted_fields_count": len(header.__dict__) + sum(len(a.__dict__) for a in activities),
            "segmented_regions": len(region_results),
        }
    )

    # Apply post-processing corrections
    processed_output = postprocess_ocr_output(raw_output)

    return processed_output


def _build_header_from_regions(header_row: Dict) -> OCRHeader:
    """Build OCRHeader from extracted text regions."""
    cols = sorted(header_row.keys())
    texts = [normalize_text_field(header_row[col].text) or "" for col in cols]

    # Try to infer header fields from position and content
    machine_id_text = texts[0] if len(texts) > 0 else None
    operator_text = texts[1] if len(texts) > 1 else None
    date_text = texts[2] if len(texts) > 2 else None
    shift_text = texts[3] if len(texts) > 3 else "day"

    return OCRHeader(
        machine_id=OCRField(
            value=machine_id_text,
            confidence=header_row.get(cols[0], None).confidence if cols else 0.0
        ),
        operator_name=OCRField(
            value=operator_text,
            confidence=header_row.get(cols[1], None).confidence if len(cols) > 1 else 0.0
        ),
        date=OCRField(
            value=date_text,
            confidence=header_row.get(cols[2], None).confidence if len(cols) > 2 else 0.0
        ),
        shift=OCRField(
            value=(shift_text.lower() if shift_text in ["day", "night", "Day", "Night"] else "day"),
            confidence=header_row.get(cols[3], None).confidence if len(cols) > 3 else 0.0
        ),
        engine_hours_start=OCRField(
            value=normalize_numeric_field(header_row.get(cols[4], None).text) if len(cols) > 4 else None,
            confidence=header_row.get(cols[4], None).confidence if len(cols) > 4 else 0.0
        ),
        engine_hours_end=OCRField(
            value=normalize_numeric_field(header_row.get(cols[5], None).text) if len(cols) > 5 else None,
            confidence=header_row.get(cols[5], None).confidence if len(cols) > 5 else 0.0
        )
    )


def _build_activity_from_row(row_idx: int, row_data: Dict) -> Optional[OCRActivityRow]:
    """Build OCRActivityRow from extracted text regions."""
    cols = sorted(row_data.keys())
    if len(cols) < 3:
        return None

    texts = {col: row_data[col].text for col in cols}
    confidences = {col: row_data[col].confidence for col in cols}

    return OCRActivityRow(
        row_index=row_idx,
        activity_code=OCRField(
            value=normalize_numeric_field(texts.get(cols[0], "")),
            confidence=confidences.get(cols[0], 0.0)
        ),
        from_time=OCRField(
            value=normalize_time_field(texts.get(cols[1], "")),
            confidence=confidences.get(cols[1], 0.0)
        ),
        to_time=OCRField(
            value=normalize_time_field(texts.get(cols[2], "")),
            confidence=confidences.get(cols[2], 0.0)
        ),
        location=OCRField(
            value=normalize_text_field(texts.get(cols[3], "")),
            confidence=confidences.get(cols[3], 0.0)
        ),
        loads=OCRField(
            value=normalize_numeric_field(texts.get(cols[4], "")) if len(cols) > 4 else None,
            confidence=confidences.get(cols[4], 0.0)
        ),
        remarks=OCRField(
            value=normalize_text_field(texts.get(cols[5], "")) if len(cols) > 5 else None,
            confidence=confidences.get(cols[5], 0.0)
        )
    )


def _calculate_total_confidence(header: OCRHeader, activities: List[OCRActivityRow]) -> float:
    """Calculate average confidence across all extracted fields."""
    all_fields = [
        header.machine_id, header.operator_name, header.date, header.shift,
        header.engine_hours_start, header.engine_hours_end
    ]
    
    for activity in activities:
        all_fields.extend([
            activity.activity_code, activity.from_time, activity.to_time,
            activity.location, activity.loads, activity.remarks
        ])

    valid_fields = [f for f in all_fields if f.value is not None]
    if not valid_fields:
        return 0.0
    
    avg_confidence = sum(f.confidence for f in valid_fields) / len(valid_fields)
    return avg_confidence
