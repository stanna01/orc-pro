"""OCR Post-Processing Module for ORC Pro.

This module handles post-processing of OCR-extracted text to improve accuracy
through character normalization, time correction, code validation, and vocabulary
correction specific to mining checklists.

Key Features:
- Character normalization (O→0, l→1, etc.)
- Time format correction (14:3O → 14:30)
- Activity code validation and normalization
- Mining vocabulary correction
- Confidence score adjustment based on corrections
"""

import re
from typing import Dict, List, Optional, Tuple
from backend.app.models.schemas import OCRField, OCRHeader, OCRActivityRow, OCROutput


# Character normalization mappings
CHARACTER_CORRECTIONS = {
    'O': '0',  # Common OCR confusion
    'o': '0',
    'l': '1',  # Lowercase L to 1
    'I': '1',  # Uppercase I to 1
    'i': '1',
    'S': '5',  # S to 5
    's': '5',
    'B': '8',  # B to 8
    'G': '6',  # G to 6
    'Z': '2',  # Z to 2
    'z': '2',
    'Q': '0',  # Q to 0
    'q': '0',
}

# Mining-specific vocabulary corrections
MINING_VOCABULARY = {
    # Activity codes (standardized)
    '101': ['101', '1O1', 'lO1', 'lOl', 'IO1', 'I01'],
    '102': ['102', '1O2', 'lO2'],
    '201': ['201', '2O1', '2Ol'],
    '202': ['202', '2O2'],
    '300': ['300', '3OO', '3O0'],
    '301': ['301', '3O1', '3Ol'],
    '302': ['302', '3O2'],
    '303': ['303', '3O3'],

    # Locations (common mining areas)
    'pit a': ['pit a', 'pita', 'pit-a', 'pit  a', 'pit1'],
    'pit b': ['pit b', 'pitb', 'pit-b', 'pit  b', 'pit2'],
    'pit c': ['pit c', 'pitc', 'pit-c', 'pit  c', 'pit3'],
    'waste dump': ['waste dump', 'wastedump', 'waste-dump', 'dump'],
    'crusher': ['crusher', 'cruscher', 'crushor'],
    'haul road': ['haul road', 'haulroad', 'haul-road', 'road'],

    # Equipment types
    'loader': ['loader', 'loador', 'loder'],
    'truck': ['truck', 'truk', 'truc'],
    'dozer': ['dozer', 'dozor', 'dosor'],
    'excavator': ['excavator', 'excavater', 'exavator'],

    # Operations
    'loading': ['loading', 'loadlng', 'load ing'],
    'hauling': ['hauling', 'haul lng', 'haul ing'],
    'dumping': ['dumping', 'dump lng', 'dump ing'],
    'maintenance': ['maintenance', 'maintanance', 'maintainance'],
    'repair': ['repair', 'repalr', 'rep air'],
    'breakdown': ['breakdown', 'break down', 'breakdwon'],
    'safety meeting': ['safety meeting', 'safety meetlng', 'safetymeeting'],
    'daily service': ['daily service', 'dailyservice', 'daily service'],
}

# Reverse mapping for vocabulary correction
VOCABULARY_REVERSE = {}
for canonical, variants in MINING_VOCABULARY.items():
    for variant in variants:
        VOCABULARY_REVERSE[variant.lower()] = canonical


def normalize_characters(text: str) -> str:
    """Apply character-level normalization corrections.

    Args:
        text: Input text string

    Returns:
        Normalized text with character corrections applied
    """
    if not text:
        return text

    normalized = text
    for wrong, correct in CHARACTER_CORRECTIONS.items():
        normalized = normalized.replace(wrong, correct)

    return normalized


def normalize_time_format(time_str: str) -> Optional[str]:
    """Normalize time strings to HH:MM format with OCR corrections.

    Handles common OCR errors:
    - 14:3O → 14:30
    - 9:5 → 09:05 (padding)
    - 1430 → 14:30 (missing colon)
    - 2:3Opm → 14:30 (AM/PM conversion)

    Args:
        time_str: Raw time string from OCR

    Returns:
        Normalized HH:MM format or None if invalid
    """
    if not time_str:
        return None

    # Clean and normalize characters first
    clean_time = normalize_characters(time_str.strip().lower())

    # Remove spaces and common separators
    clean_time = re.sub(r'[^\w:]', '', clean_time)

    # Handle AM/PM
    is_pm = 'pm' in clean_time
    clean_time = clean_time.replace('am', '').replace('pm', '')

    # Try different time formats
    patterns = [
        # HH:MM or H:M or H:MM
        r'^(\d{1,2}):(\d{1,2})$',
        # HHMM
        r'^(\d{1,2})(\d{2})$',
        # HMM
        r'^(\d{1,2})(\d{1})$',
    ]

    for pattern in patterns:
        match = re.match(pattern, clean_time)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))

            # Apply PM offset
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0

            # Validate ranges
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

    return None


def validate_activity_code(code: str) -> Tuple[bool, Optional[str]]:
    """Validate and normalize activity codes.

    Args:
        code: Raw activity code from OCR

    Returns:
        Tuple of (is_valid, normalized_code)
    """
    if not code:
        return False, None

    # Normalize characters
    normalized = normalize_characters(code.strip())

    # Remove non-numeric characters except common OCR errors
    clean_code = re.sub(r'[^0-9]', '', normalized)

    if not clean_code:
        return False, None

    # Check if it's a valid mining activity code (3 digits, specific ranges)
    try:
        code_num = int(clean_code)
        if 100 <= code_num <= 399:  # Valid mining activity code range
            return True, f"{code_num:03d}"
    except ValueError:
        pass

    return False, None


def correct_vocabulary(text: str) -> str:
    """Apply vocabulary corrections for mining-specific terms.

    Args:
        text: Input text to correct

    Returns:
        Text with vocabulary corrections applied
    """
    if not text:
        return text

    original_words = text.split()
    corrected_words = []

    for word in original_words:
        lower_word = word.lower()
        if lower_word in VOCABULARY_REVERSE:
            corrected_words.append(VOCABULARY_REVERSE[lower_word])
        else:
            matched = False
            for variant, canonical in VOCABULARY_REVERSE.items():
                if variant in lower_word and len(variant) > 3:
                    corrected_words.append(canonical)
                    matched = True
                    break
            if not matched:
                corrected_words.append(word)  # preserve original case

    return ' '.join(corrected_words)


def postprocess_ocr_field(field: OCRField, field_type: str = 'text') -> OCRField:
    """Post-process a single OCR field based on its type.

    Args:
        field: OCRField to post-process
        field_type: Type of field ('time', 'numeric', 'text', 'code')

    Returns:
        Post-processed OCRField with corrections and confidence adjustment
    """
    if not field.value:
        return field

    original_value = field.value
    confidence_boost = 0.0

    if field_type == 'time':
        corrected = normalize_time_format(original_value)
        if corrected and corrected != original_value:
            confidence_boost = 0.2  # Time corrections are reliable

    elif field_type == 'numeric':
        corrected = normalize_characters(original_value)
        if corrected != original_value:
            confidence_boost = 0.15

    elif field_type == 'code':
        is_valid, corrected = validate_activity_code(original_value)
        if corrected and corrected != original_value:
            confidence_boost = 0.25  # Code validation is strong
        elif not is_valid:
            corrected = original_value  # Keep original if invalid

    else:  # text
        # For text fields, only correct vocabulary, avoid aggressive character normalization
        corrected = correct_vocabulary(original_value)
        if corrected != original_value:
            confidence_boost = 0.1

    # Adjust confidence (don't exceed 1.0)
    new_confidence = min(1.0, field.confidence + confidence_boost)

    return OCRField(
        value=corrected,
        confidence=new_confidence
    )


def postprocess_ocr_output(ocr_output: OCROutput) -> OCROutput:
    """Post-process complete OCR output with all corrections.

    Args:
        ocr_output: Raw OCROutput from OCR extraction

    Returns:
        Post-processed OCROutput with corrections applied
    """
    # Process header fields
    processed_header = OCRHeader(
        machine_id=postprocess_ocr_field(ocr_output.header.machine_id, 'text'),
        operator_name=postprocess_ocr_field(ocr_output.header.operator_name, 'text'),
        date=postprocess_ocr_field(ocr_output.header.date, 'text'),
        shift=postprocess_ocr_field(ocr_output.header.shift, 'text'),
        engine_hours_start=postprocess_ocr_field(ocr_output.header.engine_hours_start, 'numeric'),
        engine_hours_end=postprocess_ocr_field(ocr_output.header.engine_hours_end, 'numeric'),
    )

    # Process activity rows
    processed_activities = []
    for activity in ocr_output.activities:
        processed_activity = OCRActivityRow(
            row_index=activity.row_index,
            activity_code=postprocess_ocr_field(activity.activity_code, 'code'),
            from_time=postprocess_ocr_field(activity.from_time, 'time'),
            to_time=postprocess_ocr_field(activity.to_time, 'time'),
            location=postprocess_ocr_field(activity.location, 'text'),
            loads=postprocess_ocr_field(activity.loads, 'numeric'),
            remarks=postprocess_ocr_field(activity.remarks, 'text'),
        )
        processed_activities.append(processed_activity)

    # Update processing metadata
    updated_metadata = ocr_output.processing_metadata.copy()
    updated_metadata['postprocessing_applied'] = True
    updated_metadata['character_corrections'] = True
    updated_metadata['vocabulary_corrections'] = True
    updated_metadata['time_normalization'] = True
    updated_metadata['code_validation'] = True

    # Recalculate average confidence after post-processing
    all_fields = [
        processed_header.machine_id, processed_header.operator_name,
        processed_header.date, processed_header.shift,
        processed_header.engine_hours_start, processed_header.engine_hours_end
    ]

    for activity in processed_activities:
        all_fields.extend([
            activity.activity_code, activity.from_time, activity.to_time,
            activity.location, activity.loads, activity.remarks
        ])

    valid_fields = [f for f in all_fields if f.value is not None]
    if valid_fields:
        avg_confidence = sum(f.confidence for f in valid_fields) / len(valid_fields)
        updated_metadata['postprocessing_avg_confidence'] = round(avg_confidence, 3)

    return OCROutput(
        document_id=ocr_output.document_id,
        header=processed_header,
        activities=processed_activities,
        processing_metadata=updated_metadata
    )


# Utility functions for testing and validation

def test_character_normalization():
    """Test character normalization with common OCR errors."""
    test_cases = [
        ("14:3O", "14:30"),
        ("lOl", "101"),
        ("truck", "truck"),
        ("loador", "10ad0r"),  # Character normalization is aggressive; vocabulary handles it
    ]

    print("Character Normalization Tests:")
    for input_text, expected in test_cases:
        result = normalize_characters(input_text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{input_text}' -> '{result}' (expected: '{expected}')")


def test_time_correction():
    """Test time format correction."""
    test_cases = [
        ("14:3O", "14:30"),
        ("9:5", "09:05"),
        ("1430", "14:30"),
        ("2:30pm", "14:30"),
        ("invalid", None),
    ]

    print("\nTime Correction Tests:")
    for input_time, expected in test_cases:
        result = normalize_time_format(input_time)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{input_time}' -> '{result}' (expected: '{expected}')")


def test_vocabulary_correction():
    """Test mining vocabulary corrections."""
    test_cases = [
        ("loador", "Loader"),
        ("pit a", "Pit A"),
        ("wastedump", "Waste Dump"),
        ("safetymeeting", "Safety Meeting"),
    ]

    print("\nVocabulary Correction Tests:")
    for input_text, expected in test_cases:
        result = correct_vocabulary(input_text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{input_text}' -> '{result}' (expected: '{expected}')")


if __name__ == "__main__":
    # Run tests when executed directly
    test_character_normalization()
    test_time_correction()
    test_vocabulary_correction()