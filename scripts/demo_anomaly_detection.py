from backend.app.services.rule_engine import process_checklist_timeline
from datetime import date

# Construct OCR-like payload with header engine_hours and activities
ocr_output = {
    "header": {
        "shift": {"value": "day"},
        "engine_hours": "2.0",  # 2 hours
        "activity_count": "2",
    },
    "activities": [
        {"row_index": 0, "activity_code": {"value": "101"}, "from_time": {"value": "06:00"}, "to_time": {"value": "07:00"}, "location": {"value": "Pit A"}, "loads": {"value": "2"}, "remarks": {"value": "loading"}},
        {"row_index": 1, "activity_code": {"value": "102"}, "from_time": {"value": "07:00"}, "to_time": {"value": "17:00"}, "location": {"value": "Pit B"}, "loads": {"value": "3"}, "remarks": {"value": "loading"}},
    ]
}

res = process_checklist_timeline(ocr_output, reference_date=date(2026,5,7))
print("Events:")
for e in res["events"]:
    print(e)
print("\nSummary:")
print(res["summary"]["system_consistency"])