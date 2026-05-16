from datetime import date
from backend.app.services.rule_engine import process_checklist_timeline, compute_metrics, TimelineEvent


# Build sample OCR input
ocr = {
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': {'value': '101'}, 'from_time': {'value': '06:00'}, 'to_time': {'value': '08:00'}, 'location': {'value': 'Pit A'}, 'loads': {'value': '2'}, 'remarks': {'value': 'loading'}},
        {'row_index': 1, 'activity_code': {'value': '300'}, 'from_time': {'value': '08:00'}, 'to_time': {'value': '10:00'}, 'location': {'value': 'Pit B'}, 'loads': {'value': '0'}, 'remarks': {'value': 'breakdown'}},
        {'row_index': 2, 'activity_code': {'value': '101'}, 'from_time': {'value': '10:30'}, 'to_time': {'value': '12:00'}, 'location': {'value': 'Pit A'}, 'loads': {'value': '3'}, 'remarks': {'value': 'loading'}},
        {'row_index': 3, 'activity_code': {'value': ''}, 'from_time': {'value': '12:00'}, 'to_time': {'value': '12:15'}, 'location': {'value': 'Yard'}, 'loads': {'value': '0'}, 'remarks': {'value': 'toolbox talk'}},
    ]
}

res = process_checklist_timeline(ocr, reference_date=date(2026,5,7))
print('\nEvents (from process_checklist_timeline):')
for e in res['events']:
    print(e)

print('\nSummary (from pipeline):')
print(res['summary'])

# Convert event dicts to TimelineEvent objects for compute_metrics
events_objs = [TimelineEvent(**e) for e in res['events']]
metrics = compute_metrics(events_objs, res['summary']['shift'], document_date=date(2026,5,7))
print('\nComputed metrics:')
for k, v in metrics.items():
    print(f"  {k}: {v}")

# Mismatch detection: create overlapping events intentionally
events_overlap = events_objs.copy()
# overlap by setting event 2 start earlier
events_overlap[2].start_time = '09:30'
try:
    compute_metrics(events_overlap, res['summary']['shift'], document_date=date(2026,5,7))
except Exception as ex:
    print('\nMismatch/Conflict detected as expected:')
    print(str(ex))
