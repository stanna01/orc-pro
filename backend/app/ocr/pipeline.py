"""OCR and table extraction for handwritten mining checklists."""

import re
from datetime import datetime
from typing import Dict, List, Optional


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
    """Normalize OCR text for robust matching."""
    return re.sub(r"\s+", " ", text.strip())


def extract_page1_fields(raw_text: str) -> Dict[str, Optional[str]]:
    """Extract Page 1 checklist metadata from raw OCR text."""
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
    """Extract candidate activity table rows from raw OCR text."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    header_index = None
    for index, line in enumerate(lines):
        lower = line.lower()
        if all(col in lower for col in ["activity", "from", "to", "workplace", "ore", "loads"]):
            header_index = index
            break
    if header_index is None:
        return []

    rows = []
    for line in lines[header_index + 1 :]:
        if re.search(r"machine\s*number|operator|permit|date|shift|start\s*engine", line, flags=re.IGNORECASE):
            break
        if line:
            rows.append(line)
    return rows


def parse_activity_row(line: str) -> Dict[str, Optional[str]]:
    """Parse one activity row line into the expected columns."""
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
    """Extract raw activity table entries from OCR text."""
    rows = split_activity_rows(raw_text)
    return [parse_activity_row(row) for row in rows]


def guess_shift(raw_text: str) -> Optional[str]:
    """Guess the shift value from raw text if it is missing."""
    lower = raw_text.lower()
    if "night" in lower:
        return "night"
    if "day" in lower:
        return "day"
    return None


def is_breakdown(activity_code: Optional[str], remarks: Optional[str]) -> bool:
    """Detect whether the row should be classified as a breakdown."""
    if activity_code:
        normalized = re.sub(r"\D", "", activity_code)
        if normalized.startswith("3") and len(normalized) >= 3:
            return True
    if remarks:
        lower = remarks.lower()
        return any(re.search(keyword, lower) for keyword in BREAKDOWN_KEYWORDS)
    return False
