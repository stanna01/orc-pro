# Machine Analytics Module - Formula Reference

## Overview

The analytics module (`backend/app/services/analytics.py`) computes machine performance metrics from processed timeline events and engine hours. It provides a comprehensive view of machine availability, utilization, and breakdowns across day and night shifts.

---

## Data Flow

```
OCR Output
    ↓
Rule Engine (classify events, infer times)
    ↓
Timeline Events + Engine Hours
    ↓
Analytics Module
    ↓
Performance Metrics (availability, utilization, downtime)
```

---

## Time Windows

### Day Shift
- Start: 06:00
- End: 18:00
- Duration: 12 hours = 720 minutes

### Night Shift
- Start: 18:00
- End: 06:00 (next day)
- Duration: 12 hours = 720 minutes

Note: Night shift spans midnight boundary requiring special date handling.

---

## Availability Breakdown

### Total Shift Minutes
```
total_shift_minutes = 720 (constant, 12-hour shift)
```

### Release Time Calculation
The release time marks when the machine is released to production after daily service.

```
release_time: HH:MM (extracted from last service event end time)

release_delay_minutes = shift_end - release_time

Example (day shift):
  release_time = 09:30
  shift_end = 18:00
  release_delay_minutes = 510 minutes (8.5 hours)
```

### Available Minutes (Availability)
Machine is available for production from release until breakdown or end of shift.

```
available_minutes = shift_end - release_time - breakdown_minutes

Example (day shift):
  shift_end = 18:00 (1080 min from start)
  release_time = 09:30 (570 min from start)
  breakdown_minutes = 90 min
  available_minutes = (1080 - 570) - 90 = 420 minutes
```

### Production Time
```
production_minutes = sum(event.duration_minutes for event in events 
                          if event.event_type == "production")

Example:
  Event 1: 60 min (production)
  Event 2: 90 min (production)
  Event 3: 60 min (service)
  Event 4: 210 min (production)
  Event 5: 300 min (production)
  
  production_minutes = 60 + 90 + 210 + 300 = 660 minutes
```

### Breakdown Time
```
breakdown_minutes = sum(event.duration_minutes for event in events 
                         if event.event_type == "breakdown")

Example:
  Breakdown event: 90 min (hydraulic fault)
  breakdown_minutes = 90
```

### Service Time
```
service_minutes = sum(event.duration_minutes for event in events 
                       if event.event_type == "service")

Example:
  Service event: 60 min (daily service)
  service_minutes = 60
```

### Safety Time
```
safety_minutes = sum(event.duration_minutes for event in events 
                      if event.event_type == "safety_meeting")

Example:
  Safety event: 20 min
  safety_minutes = 20
```

### Idle Time
```
idle_minutes = sum(event.duration_minutes for event in events 
                    if event.event_type == "idle")

Alternatively, computed as gaps between production events:
  Shift span: 18:00 → 06:00 (next day)
  Production: 18:00-20:00, 21:30-04:00
  Gap 1: 20:00-21:30 (90 min) → idle
  Gap 2: 04:00-06:00 (120 min) → idle
  
  idle_minutes = 90 + 120 = 210 minutes
```

---

## Engine Hours Validation

### Engine Hours Delta
```
engine_hours_delta = end_engine_hours - start_engine_hours

Validation Rules:
1. Delta must be >= 0 (hours should not decrease)
2. If production_minutes > 60 AND delta == 0 → WARNING
3. If delta > 20 → ALERT (possible meter rollover)
```

### Transmission Hours Delta
```
transmission_hours_delta = end_transmission_hours - start_transmission_hours

Same validation rules as engine hours.
```

### Relationship to Production
Expected correlation:
```
If production_minutes = 600 min (10 hours)
  Expected engine_hours_delta ≈ 10 hours
  Tolerance: ±1 hour (due to idle, safety, service time within shift)
```

---

## Performance Ratios

### Availability Ratio
```
availability_ratio = available_minutes / total_shift_minutes

Range: 0.0 to 1.0
Target: > 0.90 (90%)

Meaning: Percentage of shift when machine is available for use after service.

Example (day shift):
  available_minutes = 510
  total_shift_minutes = 720
  availability_ratio = 510 / 720 = 0.708 (70.8%)
```

### Utilization Ratio
```
utilization_ratio = production_minutes / available_minutes

Range: 0.0 to 1.0
Target: > 0.80 (80%)

Meaning: How efficiently machines uses available productive time.

Example:
  production_minutes = 420
  available_minutes = 510
  utilization_ratio = 420 / 510 = 0.824 (82.4%)
```

### Downtime Ratio (Breakdown)
```
downtime_ratio = breakdown_minutes / available_minutes

Range: 0.0 to 1.0
Target: < 0.10 (10%)

Meaning: Percentage of available time lost to machine breakdowns.

Example:
  breakdown_minutes = 90
  available_minutes = 510
  downtime_ratio = 90 / 510 = 0.176 (17.6%)
```

### Production Ratio
```
production_ratio = production_minutes / total_shift_minutes

Range: 0.0 to 1.0
Target: > 0.70 (70%)

Meaning: Actual production time as percentage of entire shift.

Example:
  production_minutes = 420
  total_shift_minutes = 720
  production_ratio = 420 / 720 = 0.583 (58.3%)
```

### Breakdown Ratio
```
breakdown_ratio = breakdown_minutes / total_shift_minutes

Range: 0.0 to 1.0
Target: < 0.05 (5%)

Meaning: Total shift impact of breakdowns.

Example:
  breakdown_minutes = 90
  total_shift_minutes = 720
  breakdown_ratio = 90 / 720 = 0.125 (12.5%)
```

### Idle Ratio
```
idle_ratio = idle_minutes / total_shift_minutes

Range: 0.0 to 1.0
Target: < 0.10 (10%)

Meaning: Unplanned gaps in the schedule.

Example:
  idle_minutes = 60
  total_shift_minutes = 720
  idle_ratio = 60 / 720 = 0.083 (8.3%)
```

### Safety Ratio
```
safety_ratio = safety_minutes / total_shift_minutes

Range: 0.0 to 1.0
Target: 0.02 to 0.05 (2-5% depending on policy)

Meaning: Planned safety and meeting time.

Example:
  safety_minutes = 30
  total_shift_minutes = 720
  safety_ratio = 30 / 720 = 0.042 (4.2%)
```

### Effective Availability Ratio
```
effective_availability_ratio = (available_minutes - idle_minutes) / total_shift_minutes

Range: 0.0 to 1.0
Target: > 0.85 (85%)

Meaning: True productible time after removing idle gaps.

Example:
  available_minutes = 510
  idle_minutes = 60
  total_shift_minutes = 720
  effective_availability_ratio = (510 - 60) / 720 = 0.625 (62.5%)
```

---

## Recommended Thresholds

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Availability Ratio | > 0.90 | 0.80–0.90 | < 0.80 |
| Utilization Ratio | > 0.80 | 0.65–0.80 | < 0.65 |
| Downtime Ratio | < 0.05 | 0.05–0.15 | > 0.15 |
| Production Ratio | > 0.70 | 0.55–0.70 | < 0.55 |
| Breakdown Ratio | < 0.05 | 0.05–0.10 | > 0.10 |
| Idle Ratio | < 0.10 | 0.10–0.20 | > 0.20 |
| Engine Hours Valid | Yes | — | No |

---

## Input Example

```python
events = [
    {
        "activity_code": "101",
        "start_time": "06:00",
        "end_time": "07:00",
        "duration_minutes": 60.0,
        "event_type": "production",
    },
    {
        "activity_code": "200",
        "start_time": "07:00",
        "end_time": "08:00",
        "duration_minutes": 60.0,
        "event_type": "service",
        "is_daily_service": True,
    },
    # ... more events
]

analytics = compute_machine_analytics(
    events=events,
    shift="day",
    release_time="08:00",
    start_engine_hours=1200.0,
    end_engine_hours=1212.3,
    start_transmission_hours=800.0,
    end_transmission_hours=810.2,
)
```

---

## Output Example

```json
{
  "availability_breakdown": {
    "total_shift_minutes": 720,
    "release_time": "08:00",
    "release_delay_minutes": 600,
    "available_minutes": 600,
    "production_minutes": 420,
    "breakdown_minutes": 90,
    "service_minutes": 60,
    "safety_minutes": 0,
    "idle_minutes": 30
  },
  "engine_hours_metrics": {
    "start_engine_hours": 1200.0,
    "end_engine_hours": 1212.3,
    "engine_hours_delta": 12.3,
    "start_transmission_hours": 800.0,
    "end_transmission_hours": 810.2,
    "transmission_hours_delta": 10.2,
    "engine_hours_valid": true,
    "validation_message": null
  },
  "performance_ratios": {
    "availability_ratio": 0.833,
    "utilization_ratio": 0.7,
    "downtime_ratio": 0.15,
    "production_ratio": 0.583,
    "breakdown_ratio": 0.125,
    "idle_ratio": 0.042,
    "safety_ratio": 0.0,
    "effective_availability_ratio": 0.792
  }
}
```

---

## Usage

### Basic Usage
```python
from backend.app.services.analytics import compute_machine_analytics

result = compute_machine_analytics(
    events=timeline_events,
    shift="day",
    release_time="09:30",
    start_engine_hours=1200.0,
    end_engine_hours=1212.3,
)

availability = result["availability_breakdown"]
performance = result["performance_ratios"]

print(f"Availability: {performance['availability_ratio']:.2%}")
print(f"Utilization: {performance['utilization_ratio']:.2%}")
```

### Component-wise Usage
```python
from backend.app.services.analytics import (
    compute_availability_breakdown,
    compute_engine_hours_metrics,
    compute_performance_ratios,
)

# Step 1: Availability
avail = compute_availability_breakdown(events, "day", "09:30")

# Step 2: Engine validation
engine = compute_engine_hours_metrics(1200.0, 1212.3, 800.0, 810.2)

# Step 3: Ratios
perf = compute_performance_ratios(avail, engine)

print(perf.to_dict())
```

---

## Notes

- All time computations normalized to minutes for consistency
- Night shift times automatically adjusted for midnight boundary
- Idle gaps computed as intervals between non-idle events within shift window
- Engine hours delta validated against production time for sanity checks
- All ratios returned as floats (0.0 to 1.0) for consistency with float formatting
