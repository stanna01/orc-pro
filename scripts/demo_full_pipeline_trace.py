try:
    from backend.app.services.orchestrator import ChecklistProcessingOrchestrator
except Exception:
    # Fallback: import locally to allow demo in minimal environments
    from backend.app.services.orchestrator import ChecklistProcessingOrchestrator


# Synthetic OCR-extracted regions (header regions first, then activity regions)
extracted_texts = [
    {"region_index": 0, "text": "Machine: LOAD-1 Operator: Alice Shift: day Engine hours: 100.0 102.0", "confidence": 0.9, "classification": "high"},
    {"region_index": 1, "text": "Date: 2026-05-07", "confidence": 0.85, "classification": "high"},
    {"region_index": 2, "text": "06:00 07:00 PitA 2 loading", "confidence": 0.8, "classification": "medium"},
    {"region_index": 3, "text": "07:00 12:00 PitB 5 loading", "confidence": 0.78, "classification": "medium"},
    {"region_index": 4, "text": "12:00 14:00 PitC 0 breakdown", "confidence": 0.6, "classification": "low"},
]

orc = ChecklistProcessingOrchestrator(db=None)
res = orc.process_from_extracted_regions(extracted_texts)

print('\nPIPELINE TRACE')
for l in res['processing_log']:
    print(f"[{l['stage']}] {l['status'].upper()}: {l['message']}")

print('\nFINAL SUMMARY')
print('success:', res.get('success'))
if res.get('integration_result'):
    print('events:', res['integration_result'].get('events'))
    print('analytics:', res['integration_result'].get('analytics'))
else:
    print('validation_report:', res.get('validation_report'))
