from datetime import date
from backend.app.services.rule_engine import process_checklist_timeline


def run_case(name, ocr_output):
    print('\n===', name, '===')
    res = process_checklist_timeline(ocr_output, reference_date=date(2026,5,7))
    for e in res['events']:
        print(e)
    print('Summary:', res['summary'])


# Case 1: Night shift crossing midnight
def f(v):
    return {'value': v} if v is not None else {'value': None}

ocr_night = {
    'header': {'shift': {'value': 'night'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('101'), 'from_time': f('23:30'), 'to_time': f('00:30'), 'location': f('Pit A'), 'loads': f('1'), 'remarks': f('')},
    ]
}

# Case 2: Missing end time inferred from next start
ocr_missing_end = {
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('101'), 'from_time': f('08:00'), 'to_time': f(None), 'location': f('Pit A'), 'loads': f('2'), 'remarks': f('')},
        {'row_index': 1, 'activity_code': f('102'), 'from_time': f('10:00'), 'to_time': f('11:00'), 'location': f('Pit B'), 'loads': f('1'), 'remarks': f('')},
    ]
}

# Case 3: Invalid wrap (day shift end earlier than start) - should be rejected/flagged
ocr_invalid_wrap = {
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('101'), 'from_time': f('15:00'), 'to_time': f('14:00'), 'location': f('Pit A'), 'loads': f('2'), 'remarks': f('')},
    ]
}

run_case('Night crossing-midnight', ocr_night)
run_case('Missing end-time inference', ocr_missing_end)
run_case('Invalid wrap rejected', ocr_invalid_wrap)
