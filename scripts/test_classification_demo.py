from datetime import date
from backend.app.services.rule_engine import process_checklist_timeline


def run_case(name, ocr_output):
    print('\n===', name, '===')
    res = process_checklist_timeline(ocr_output, reference_date=date(2026,5,7))
    for e in res['events']:
        print(f"row {e['row_index']}: type={e['event_type']} ambiguous={e['is_ambiguous']} reasons={e.get('inference_reasons')}")


# Prepare helper
def f(v):
    return {'value': v} if v is not None else {'value': None}

# 5 real classification examples
examples = []
# 1 Breakdown (remark)
examples.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('101'), 'from_time': f('09:00'), 'to_time': f('12:30'), 'location': f('Pit A'), 'loads': f('0'), 'remarks': f('hydraulic leak - stalled')},
    ]
})
# 2 Delay (remark)
examples.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f(''), 'from_time': f('10:15'), 'to_time': f('10:20'), 'location': f('Road'), 'loads': f('0'), 'remarks': f('waiting on truck')},
    ]
})
# 3 Safety
examples.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f(''), 'from_time': f('06:15'), 'to_time': f('06:30'), 'location': f('Yard'), 'loads': f('0'), 'remarks': f('toolbox talk - safety')},
    ]
})
# 4 Service (code + remark)
examples.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('200'), 'from_time': f('07:00'), 'to_time': f('07:45'), 'location': f('Depot'), 'loads': f('0'), 'remarks': f('daily service - greasing')},
    ]
})
# 5 Production (mining ops hints)
examples.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('101'), 'from_time': f('08:00'), 'to_time': f('08:30'), 'location': f('Pit A'), 'loads': f('3'), 'remarks': f('loading and hauling')},
    ]
})

# Ambiguous cases
ambiguous = []
# 1 unclear short remark
ambiguous.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f(''), 'from_time': f('09:00'), 'to_time': f('09:02'), 'location': f('Pit A'), 'loads': f('1'), 'remarks': f('work')},
    ]
})
# 2 conflicting signals (code suggests breakdown but remarks empty and short duration)
ambiguous.append({
    'header': {'shift': {'value': 'day'}},
    'activities': [
        {'row_index': 0, 'activity_code': f('300'), 'from_time': f('11:00'), 'to_time': f('11:05'), 'location': f('Pit B'), 'loads': f('0'), 'remarks': f('')},
    ]
})

for i, ex in enumerate(examples, 1):
    run_case(f"Example {i}", ex)

for i, ex in enumerate(ambiguous, 1):
    run_case(f"Ambiguous {i}", ex)
