from datetime import date
from backend.app.services.rule_engine import process_checklist_timeline

# Overlap case where first event has inferred end and can be adjusted
ocr = {
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': {'value': '101'}, 'from_time': {'value': '08:00'}, 'to_time': {'value': None}, 'location': {'value': 'Pit A'}, 'loads': {'value': '2'}, 'remarks': {'value': ''}},
        {'row_index': 1, 'activity_code': {'value': '102'}, 'from_time': {'value': '09:00'}, 'to_time': {'value': '10:00'}, 'location': {'value': 'Pit B'}, 'loads': {'value': '1'}, 'remarks': {'value': ''}},
    ]
}

res = process_checklist_timeline(ocr, reference_date=date(2026,5,7))
print('\nEvents:')
for e in res['events']:
    print(e)

print('\nSummary:')
print(res['summary'])

if 'consistency' in res['summary']:
    print('\nConsistency report:')
    print(res['summary']['consistency'])
else:
    print('\nNo consistency issues; timeline allowed into analytics.')
