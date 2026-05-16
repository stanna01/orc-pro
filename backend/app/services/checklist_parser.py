"""Checklist parser - converts raw OCR text to structured data."""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime, date

from backend.app.models.schemas import (
    OCROutput, OCRHeader, OCRField, OCRActivityRow
)


# Normalization table for common OCR misreads
_NORMALIZE_MAP = str.maketrans({
    'O': '0',
    'o': '0',
    'I': '1',
    'l': '1',
    'B': '8',
    'S': '5',
    's': '5',
    '\\|': '1',
    ',': ':',
    ';': ':',
    '‘': "'",
    '’': "'",
})


def normalize_text_for_parser(text: str) -> str:
    if not text:
        return ""
    # Replace common misreads
    t = text.translate(_NORMALIZE_MAP)
    # Remove noise characters except colon, digits, letters, space and slash
    t = re.sub(r"[^A-Za-z0-9:\/\s\-\.\,]", "", t)
    # Normalize multiple spaces and punctuation
    t = re.sub(r"[\,\.]+", ":", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def levenshtein(a: str, b: str) -> int:
    # simple DP implementation
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, lb + 1):
            cur = dp[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur
    return dp[lb]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    a = a.lower()
    b = b.lower()
    dist = levenshtein(a, b)
    return 1.0 - dist / max(len(a), len(b))


def fuzzy_keyword_search(text: str, keywords: List[str], thresh: float = 0.7) -> Optional[str]:
    best = (None, 0.0)
    for k in keywords:
        score = similarity(normalize_text_for_parser(text), k)
        if score > best[1]:
            best = (k, score)
    return best[0] if best[1] >= thresh else None


def parse_time_tolerant(text: str) -> Dict[str, Any]:
    """Try to parse messy time strings into HH:MM. Returns dict with parsed, original, score, valid."""
    original = text
    if not text:
        return {"parsed": None, "original": original, "score": 0.0, "valid": False}
    t = normalize_text_for_parser(text)
    # Replace common separators
    t = t.replace(' ', '').replace('-', '').replace('/', '').replace('.', ':')
    # Fix characters like O->0 etc already in normalization
    # Try patterns: HH:MM, H:MM, HHMM, HMM
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", t)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            parsed = f"{hh:02d}:{mm:02d}"
            return {"parsed": parsed, "original": original, "score": 0.95, "valid": True}
        # try to correct swapped digits
    m = re.match(r"^(\d{3,4})$", t)
    if m:
        s = m.group(1)
        if len(s) == 3:
            hh = int(s[0])
            mm = int(s[1:])
        else:
            hh = int(s[:2])
            mm = int(s[2:])
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            parsed = f"{hh:02d}:{mm:02d}"
            return {"parsed": parsed, "original": original, "score": 0.9, "valid": True}
    # attempt to recover partial like '8' -> 08:00
    m = re.match(r"^(\d{1,2})$", t)
    if m:
        hh = int(m.group(1))
        if 0 <= hh <= 23:
            return {"parsed": f"{hh:02d}:00", "original": original, "score": 0.75, "valid": True}
    # attempt to fix common OCR: e.g. '0B:3O' -> replace letters then re-run
    t2 = ''.join(ch if ch.isdigit() or ch == ':' else '0' if ch.upper() == 'O' else ch for ch in t)
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", t2)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return {"parsed": f"{hh:02d}:{mm:02d}", "original": original, "score": 0.85, "valid": True}
    return {"parsed": None, "original": original, "score": 0.0, "valid": False}


def parse_code_tolerant(text: str, known_codes: List[str]) -> Dict[str, Any]:
    original = text
    if not text:
        return {"parsed": None, "original": original, "score": 0.0, "valid": False}
    t = normalize_text_for_parser(text)
    # Extract digits
    digits = re.sub(r"[^0-9]", "", t)
    if 2 <= len(digits) <= 3:
        # exact numeric code
        return {"parsed": digits, "original": original, "score": 0.95, "valid": True}
    # fuzzy against known codes
    best = (None, 0.0)
    for code in known_codes:
        score = similarity(digits or t, code)
        if score > best[1]:
            best = (code, score)
    if best[1] >= 0.7:
        return {"parsed": best[0], "original": original, "score": best[1], "valid": True}
    return {"parsed": None, "original": original, "score": 0.0, "valid": False}


class ChecklistParser:
    """Parse OCR text from mining checklists into structured format."""
    
    # Regular expressions for parsing
    TIME_PATTERN = r'(\d{1,2}):(\d{2})\s*(?:am|pm)?'
    DATE_PATTERN = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
    CODE_PATTERN = r'\b(\d{2,3})\b'
    LOADS_PATTERN = r'(\d+)\s*(?:loads?|units?)?'
    
    def __init__(self):
        self.activity_codes = {
            '101': 'Production',
            '102': 'Production',
            '103': 'Production',
            '200': 'Service',
            '201': 'Service',
            '300': 'Service',
            '400': 'Maintenance',
            '500': 'Breakdown',
            '600': 'Delay',
        }
        self.keyword_groups = {
            'breakdown': ['breakdown', 'hydraulic', 'fault', 'stuck', 'repair', 'engine failure', 'trouble', 'not moving'],
            'safety': ['safety meeting', 'toolbox talk', 'safety briefing', 'pre-shift meeting'],
            'service': ['daily service', 'service', 'maintenance', 'inspection', 'check'],
            'delay': ['delay', 'waiting', 'queue', 'standby', 'hold', 'break']
        }
    
    def parse_header(self, raw_text: str) -> OCRHeader:
        """Parse checklist header information.
        
        Args:
            raw_text: Raw OCR text from header region
            
        Returns:
            OCRHeader with extracted information
        """
        # Accept either raw string or OCR extraction dict from OCR extractor
        if isinstance(raw_text, dict):
            text_blob = raw_text.get("text", "")
            row_conf = raw_text.get("confidence")
            classification = raw_text.get("classification")
        else:
            text_blob = raw_text
            row_conf = 0.0
            classification = None

        # Extract date
        date_match = re.search(self.DATE_PATTERN, text_blob)
        date_str = date_match.group(0) if date_match else str(date.today())

        # Extract operator name (usually after "Operator:" or "Driver:")
        operator_match = re.search(r'(?:operator|driver|name)[\s:]*([A-Za-z\s]+)', text_blob, re.IGNORECASE)
        operator = operator_match.group(1).strip() if operator_match else "Unknown"

        # Extract machine ID
        machine_match = re.search(r'(?:machine|equipment|vehicle)[\s:]*([A-Z0-9\-]+)', text_blob, re.IGNORECASE)
        machine_id = machine_match.group(1) if machine_match else "UNKNOWN"

        # Extract shift
        shift = "night" if "night" in text_blob.lower() else "day"

        # Extract engine hours
        engine_matches = re.findall(r'engine\s*hours?[\s:]*(\d+\.?\d*)', text_blob, re.IGNORECASE)
        engine_hours_start = engine_matches[0] if engine_matches else None
        engine_hours_end = engine_matches[1] if len(engine_matches) > 1 else None

        return OCRHeader(
            machine_id=OCRField(value=machine_id if row_conf and row_conf >= 0.7 else None, confidence=row_conf or 0.0, classification=classification),
            operator_name=OCRField(value=operator if row_conf and row_conf >= 0.7 else None, confidence=row_conf or 0.0, classification=classification),
            date=OCRField(value=date_str if row_conf and row_conf >= 0.7 else None, confidence=row_conf or 0.0, classification=classification),
            shift=OCRField(value=shift if row_conf and row_conf >= 0.7 else None, confidence=row_conf or 0.0, classification=classification),
            engine_hours_start=OCRField(value=engine_hours_start or None, confidence=row_conf or 0.0, classification=classification),
            engine_hours_end=OCRField(value=engine_hours_end or None, confidence=row_conf or 0.0, classification=classification),
        )
    
    def parse_activity_row(self, raw_text: str, row_index: int) -> OCRActivityRow:
        """Parse a single activity row.
        
        Args:
            raw_text: Raw OCR text for the row
            row_index: Row index
            
        Returns:
            OCRActivityRow with extracted data
        """
        # Accept either raw string or OCR extraction dict
        if isinstance(raw_text, dict):
            text_blob = raw_text.get("text", "")
            row_conf = float(raw_text.get("confidence") or 0.0)
            classification = raw_text.get("classification")
            bbox = tuple(raw_text.get("bbox")) if raw_text.get("bbox") else None
        else:
            text_blob = raw_text
            row_conf = 0.0
            classification = None
            bbox = None

        # Extract activity code using tolerant parser
        raw_code = None
        # try direct search for digits first
        m_code = re.search(r"[A-Za-z0-9]{2,5}", text_blob)
        if m_code:
            raw_code = m_code.group(0)
        code_result = parse_code_tolerant(raw_code or text_blob, list(self.activity_codes.keys()))
        activity_code = code_result.get('parsed')
        code_parse_score = code_result.get('score')

        # Extract times
        # Parse times with tolerant parser
        # attempt to find tokens that look like times
        token_candidates = re.findall(r"[0-9OIl:]{1,6}", text_blob)
        from_time = None
        to_time = None
        time_scores = []
        if token_candidates:
            if len(token_candidates) >= 1:
                p = parse_time_tolerant(token_candidates[0])
                if p['valid']:
                    from_time = p['parsed']
                    time_scores.append(p['score'])
            if len(token_candidates) >= 2:
                p2 = parse_time_tolerant(token_candidates[1])
                if p2['valid']:
                    to_time = p2['parsed']
                    time_scores.append(p2['score'])

        # Extract location
        # Fuzzy location extraction: look for known prefixes and take remainder
        location = None
        m_loc = re.search(r'(pit|area|location|zone)[\s:]*([A-Za-z0-9\s]+)', text_blob, re.IGNORECASE)
        if m_loc:
            location = m_loc.group(2).strip()
        else:
            # fallback: take last token as location candidate
            parts = text_blob.strip().split()
            if len(parts) >= 2:
                location = parts[-2] if parts[-1].isdigit() else parts[-1]

        # Extract loads
        loads_match = re.search(self.LOADS_PATTERN, text_blob)
        loads = loads_match.group(1) if loads_match else None
        if not loads:
            # try to recover single-digit misreads
            t_tmp = normalize_text_for_parser(text_blob)
            m = re.search(r"(\d+)", t_tmp)
            if m:
                loads = m.group(1)

        # Detect ore/waste
        ore_waste = None
        kw = fuzzy_keyword_search(text_blob, ['ore', 'waste'], thresh=0.6)
        if kw:
            ore_waste = kw

        # Extract remarks
        remarks = text_blob.strip() if text_blob else None

        # Determine parsing confidence adjustment: combine OCR confidence, code/time parse scores
        # parsing_score ranges 0..1
        parsing_score = 0.0
        # code_parse_score defined above; time_scores may have entries
        parsing_components = []
        if 'code_parse_score' in locals():
            parsing_components.append(code_parse_score or 0.0)
        if time_scores:
            parsing_components.extend(time_scores)
        if parsing_components:
            parsing_score = sum(parsing_components) / len(parsing_components)
        # Adjusted confidence: weighted (OCR 0.6, parsing 0.4)
        adjusted_conf = round((row_conf * 0.6) + (parsing_score * 0.4), 3)

        # If the row-level confidence is low, do not populate values (prevent downstream using them)
        # Build OCRField objects with parsed/original/adjusted scores
        def _mk_field(orig_text, parsed_val, field_conf, parsed_score, is_valid_flag):
            return OCRField(
                value=parsed_val,
                confidence=field_conf,
                classification=classification,
                bbox=bbox,
                original_value=orig_text,
                parsed_value=parsed_val,
                confidence_adjusted_score=round((field_conf or 0.0) * 0.6 + (parsed_score or 0.0) * 0.4, 3),
                is_valid=is_valid_flag,
            )

        return OCRActivityRow(
            row_index=row_index,
            activity_code=_mk_field(raw_code, activity_code, row_conf, code_parse_score if 'code_parse_score' in locals() else 0.0, bool(activity_code)),
            from_time=_mk_field(token_candidates[0] if token_candidates else None, from_time, row_conf, time_scores[0] if time_scores else 0.0, bool(from_time)),
            to_time=_mk_field(token_candidates[1] if len(token_candidates) > 1 else None, to_time, row_conf, time_scores[1] if len(time_scores) > 1 else 0.0, bool(to_time)),
            location=_mk_field(None, location, row_conf, 0.8 if location else 0.0, bool(location)),
            loads=_mk_field(None, loads, row_conf, 0.9 if loads else 0.0, bool(loads)),
            remarks=_mk_field(None, remarks, row_conf, 0.6 if remarks else 0.0, bool(remarks)),
        )
    
    def parse_checklist(
        self,
        header_text: str,
        activity_texts: List[str],
        document_id: str = "auto_generated"
    ) -> OCROutput:
        """Parse complete checklist from OCR text.
        
        Args:
            header_text: Raw OCR text from header section
            activity_texts: List of raw OCR texts for each activity row
            document_id: Unique document identifier
            
        Returns:
            OCROutput with structured checklist data
        """
        # Parse header
        header = self.parse_header(header_text)
        
        # Parse activities
        activities = []
        for i, text in enumerate(activity_texts):
            if text.strip():  # Skip empty rows
                activity = self.parse_activity_row(text, i)
                activities.append(activity)
        
        return OCROutput(
            document_id=document_id,
            header=header,
            activities=activities,
            processing_metadata={
                "parser": "ChecklistParser",
                "parsing_timestamp": datetime.utcnow().isoformat(),
                "activity_count": len(activities),
                "confidence_average": float(
                    (
                        sum((getattr(a.from_time, 'confidence', 0.0) or 0.0) for a in activities) +
                        sum((getattr(a.to_time, 'confidence', 0.0) or 0.0) for a in activities) +
                        sum((getattr(a.activity_code, 'confidence', 0.0) or 0.0) for a in activities)
                    ) / (max(1, len(activities) * 3))
                ),
            }
        )


def parse_extracted_text(
    header_text: str,
    activity_texts: List[str],
    document_id: str = "auto_generated"
) -> OCROutput:
    """Parse extracted text from PDF into OCROutput.
    
    Convenience function for direct parsing.
    
    Args:
        header_text: Header section text
        activity_texts: Activity rows text list
        document_id: Document identifier
        
    Returns:
        Parsed OCROutput
    """
    parser = ChecklistParser()
    return parser.parse_checklist(header_text, activity_texts, document_id)


if __name__ == "__main__":
    # Demo: show tolerant parsing on messy OCR examples and failed flags
    demo_examples = [
        "IO:3O 15,45  pit_A  4Z lo@ds  ore",  # messy times, O->0, Z noise
        "10*30 13*OO  p1tB  42 loads  Waste",  # O->0, l->1, B->8
        "lO1 0B:3O 09:OO PitA 3 loads",        # mixed OCR digits
        "101 8 30 Pit-A 2 loads",              # partial time
        "1O3 18:6O PitC oo loads",             # invalid minute '6O' and 'oo'
    ]

    parser = ChecklistParser()
    print("\n=== TOLERANT PARSER DEMO ===\n")
    for i, ex in enumerate(demo_examples):
        row = parser.parse_activity_row({'text': ex, 'confidence': 0.65, 'classification': 'low', 'bbox': None}, i)
        print(f"Example {i+1}: ORIGINAL='{ex}'")
        print(f"  activity_code: parsed={row.activity_code.parsed_value} original={row.activity_code.original_value} adj_conf={row.activity_code.confidence_adjusted_score} valid={row.activity_code.is_valid}")
        print(f"  from_time: parsed={row.from_time.parsed_value} original={row.from_time.original_value} adj_conf={row.from_time.confidence_adjusted_score} valid={row.from_time.is_valid}")
        print(f"  to_time:   parsed={row.to_time.parsed_value} original={row.to_time.original_value} adj_conf={row.to_time.confidence_adjusted_score} valid={row.to_time.is_valid}")
        print(f"  loads:     parsed={row.loads.parsed_value} original={row.loads.original_value} adj_conf={row.loads.confidence_adjusted_score} valid={row.loads.is_valid}")
        print(f"  remarks:   {row.remarks.original_value}\n")

    # Show two failed parse cases
    failed_examples = [
        "XYZ ABC ???",    # no useful info
        "-- :: -- ::"      # non-parseable garbage
    ]
    print("=== FAILED PARSES (FLAGGED) ===\n")
    for i, ex in enumerate(failed_examples):
        row = parser.parse_activity_row({'text': ex, 'confidence': 0.2, 'classification': 'unreadable', 'bbox': None}, i)
        print(f"Failed {i+1}: ORIGINAL='{ex}' -> from_time.valid={row.from_time.is_valid}, activity_code.valid={row.activity_code.is_valid}, loads.valid={row.loads.is_valid}")
