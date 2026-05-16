"""Examples and tests for the machine analytics module."""

from backend.app.services.analytics import (
    compute_engine_hours_metrics,
    compute_availability_breakdown,
    compute_performance_ratios,
    compute_machine_analytics,
)


# ============================================================================
# Example 1: Normal production shift with service
# ============================================================================

EXAMPLE_1_EVENTS = [
    {
        "row_index": 1,
        "activity_code": "101",
        "start_time": "06:00",
        "end_time": "07:00",
        "duration_minutes": 60.0,
        "location": "Pit A",
        "loads": "4",
        "remarks": "Normal",
        "event_type": "production",
    },
    {
        "row_index": 2,
        "activity_code": "101",
        "start_time": "07:00",
        "end_time": "08:30",
        "duration_minutes": 90.0,
        "location": "Pit A",
        "loads": "5",
        "remarks": "Normal",
        "event_type": "production",
    },
    {
        "row_index": 3,
        "activity_code": "200",
        "start_time": "08:30",
        "end_time": "09:30",
        "duration_minutes": 60.0,
        "location": "Service Bay",
        "loads": "0",
        "remarks": "Daily service",
        "event_type": "service",
        "is_daily_service": True,
    },
    {
        "row_index": 4,
        "activity_code": "101",
        "start_time": "09:30",
        "end_time": "13:00",
        "duration_minutes": 210.0,
        "location": "Pit A",
        "loads": "6",
        "remarks": "Normal",
        "event_type": "production",
    },
    {
        "row_index": 5,
        "activity_code": "101",
        "start_time": "13:00",
        "end_time": "18:00",
        "duration_minutes": 300.0,
        "location": "Pit A",
        "loads": "7",
        "remarks": "Normal",
        "event_type": "production",
    },
]

# Run example 1
print("=" * 80)
print("EXAMPLE 1: Normal day shift (production 06:00-18:00 with service)")
print("=" * 80)

avail_1 = compute_availability_breakdown(EXAMPLE_1_EVENTS, shift="day", release_time="09:30")
print("\n[AVAILABILITY BREAKDOWN]")
print(f"  Total shift: {avail_1.total_shift_minutes} min (12 hours)")
print(f"  Release time: {avail_1.release_time}")
print(f"  Release delay: {avail_1.release_delay_minutes} min")
print(f"  Available minutes: {avail_1.available_minutes} min")
print(f"  Production: {avail_1.production_minutes} min")
print(f"  Service: {avail_1.service_minutes} min")
print(f"  Breakdown: {avail_1.breakdown_minutes} min")
print(f"  Safety: {avail_1.safety_minutes} min")
print(f"  Idle: {avail_1.idle_minutes} min")

engine_1 = compute_engine_hours_metrics(
    start_engine_hours=1200.0,
    end_engine_hours=1212.3,
    start_transmission_hours=800.0,
    end_transmission_hours=810.2,
    production_minutes=avail_1.production_minutes,
)
print("\n[ENGINE HOURS METRICS]")
print(f"  Engine start: {engine_1.start_engine_hours} hours")
print(f"  Engine end: {engine_1.end_engine_hours} hours")
print(f"  Engine delta: {engine_1.engine_hours_delta} hours")
print(f"  Transmission start: {engine_1.start_transmission_hours} hours")
print(f"  Transmission end: {engine_1.end_transmission_hours} hours")
print(f"  Transmission delta: {engine_1.transmission_hours_delta} hours")
print(f"  Engine valid: {engine_1.engine_hours_valid}")
if engine_1.validation_message:
    print(f"  Message: {engine_1.validation_message}")

perf_1 = compute_performance_ratios(avail_1, engine_1)
print("\n[PERFORMANCE RATIOS]")
print(f"  Availability: {perf_1.availability_ratio:.2%}")
print(f"  Utilization: {perf_1.utilization_ratio:.2%}")
print(f"  Downtime: {perf_1.downtime_ratio:.2%}")
print(f"  Production: {perf_1.production_ratio:.2%}")
print(f"  Breakdown: {perf_1.breakdown_ratio:.2%}")
print(f"  Idle: {perf_1.idle_ratio:.2%}")
print(f"  Safety: {perf_1.safety_ratio:.2%}")
print(f"  Effective availability: {perf_1.effective_availability_ratio:.2%}")

# ============================================================================
# Example 2: Night shift with breakdown
# ============================================================================

EXAMPLE_2_EVENTS = [
    {
        "row_index": 1,
        "activity_code": "101",
        "start_time": "18:00",
        "end_time": "20:00",
        "duration_minutes": 120.0,
        "location": "Pit B",
        "loads": "3",
        "remarks": "Normal",
        "event_type": "production",
    },
    {
        "row_index": 2,
        "activity_code": "300",
        "start_time": "20:00",
        "end_time": "21:30",
        "duration_minutes": 90.0,
        "location": "Pit B",
        "loads": "0",
        "remarks": "Hydraulic fault",
        "event_type": "breakdown",
        "is_breakdown": True,
    },
    {
        "row_index": 3,
        "activity_code": "200",
        "start_time": "21:30",
        "end_time": "22:30",
        "duration_minutes": 60.0,
        "location": "Service Bay",
        "loads": "0",
        "remarks": "Daily service",
        "event_type": "service",
        "is_daily_service": True,
    },
    {
        "row_index": 4,
        "activity_code": "101",
        "start_time": "22:30",
        "end_time": "04:00",
        "duration_minutes": 330.0,
        "location": "Pit B",
        "loads": "4",
        "remarks": "Normal",
        "event_type": "production",
    },
]

print("\n\n" + "=" * 80)
print("EXAMPLE 2: Night shift (18:00-06:00) with breakdown")
print("=" * 80)

avail_2 = compute_availability_breakdown(EXAMPLE_2_EVENTS, shift="night", release_time="22:30")
print("\n[AVAILABILITY BREAKDOWN]")
print(f"  Total shift: {avail_2.total_shift_minutes} min (12 hours)")
print(f"  Release time: {avail_2.release_time}")
print(f"  Release delay: {avail_2.release_delay_minutes} min")
print(f"  Available minutes: {avail_2.available_minutes} min")
print(f"  Production: {avail_2.production_minutes} min")
print(f"  Service: {avail_2.service_minutes} min")
print(f"  Breakdown: {avail_2.breakdown_minutes} min")
print(f"  Idle: {avail_2.idle_minutes} min")

engine_2 = compute_engine_hours_metrics(
    start_engine_hours=1212.3,
    end_engine_hours=1220.0,
    start_transmission_hours=810.2,
    end_transmission_hours=815.0,
    production_minutes=avail_2.production_minutes,
)
print("\n[ENGINE HOURS METRICS]")
print(f"  Engine delta: {engine_2.engine_hours_delta} hours")
print(f"  Transmission delta: {engine_2.transmission_hours_delta} hours")
print(f"  Engine valid: {engine_2.engine_hours_valid}")

perf_2 = compute_performance_ratios(avail_2, engine_2)
print("\n[PERFORMANCE RATIOS]")
print(f"  Availability: {perf_2.availability_ratio:.2%}")
print(f"  Utilization: {perf_2.utilization_ratio:.2%}")
print(f"  Downtime (breakdown): {perf_2.downtime_ratio:.2%}")
print(f"  Production: {perf_2.production_ratio:.2%}")

# ============================================================================
# Example 3: Full end-to-end analytics
# ============================================================================

print("\n\n" + "=" * 80)
print("EXAMPLE 3: Complete machine analytics computation")
print("=" * 80)

full_analytics = compute_machine_analytics(
    events=EXAMPLE_1_EVENTS,
    shift="day",
    release_time="09:30",
    start_engine_hours=1200.0,
    end_engine_hours=1212.3,
    start_transmission_hours=800.0,
    end_transmission_hours=810.2,
)

print("\n[FULL ANALYTICS OUTPUT]")
print("\nAvailability Breakdown:")
for key, value in full_analytics["availability_breakdown"].items():
    if isinstance(value, float):
        print(f"  {key}: {value:.2f}")
    else:
        print(f"  {key}: {value}")

print("\nEngine Hours Metrics:")
for key, value in full_analytics["engine_hours_metrics"].items():
    if isinstance(value, float):
        print(f"  {key}: {value:.4f}")
    else:
        print(f"  {key}: {value}")

print("\nPerformance Ratios:")
for key, value in full_analytics["performance_ratios"].items():
    if isinstance(value, float):
        print(f"  {key}: {value:.2%}")
    else:
        print(f"  {key}: {value}")

# ============================================================================
# Example 4: Invalid engine hours (alert case)
# ============================================================================

print("\n\n" + "=" * 80)
print("EXAMPLE 4: Invalid engine hours validation")
print("=" * 80)

invalid_engine = compute_engine_hours_metrics(
    start_engine_hours=1200.0,
    end_engine_hours=1195.0,  # INVALID: hours went down
    start_transmission_hours=800.0,
    end_transmission_hours=810.0,
    production_minutes=600.0,
)
print(f"\nEngine valid: {invalid_engine.engine_hours_valid}")
print(f"Validation message: {invalid_engine.validation_message}")
print(f"Engine delta: {invalid_engine.engine_hours_delta}")

print("\n\n" + "=" * 80)
print("PERFORMANCE METRICS INTERPRETATION GUIDE")
print("=" * 80)

guide = """
AVAILABILITY_RATIO (Availability)
  Formula: available_minutes / total_shift_minutes
  Target: > 90%
  Meaning: Percentage of shift time machine is available for production after release

UTILIZATION_RATIO (Utilization)
  Formula: production_minutes / available_minutes
  Target: > 80%
  Meaning: How efficiently the available time is used for actual production

DOWNTIME_RATIO (Downtime)
  Formula: breakdown_minutes / available_minutes
  Target: < 10%
  Meaning: Percentage of available time lost to breakdowns

PRODUCTION_RATIO (Production)
  Formula: production_minutes / total_shift_minutes
  Target: > 70%
  Meaning: Percentage of entire shift spent in actual production

BREAKDOWN_RATIO
  Formula: breakdown_minutes / total_shift_minutes
  Target: < 5%
  Meaning: Impact of breakdowns on total shift

IDLE_RATIO
  Formula: idle_minutes / total_shift_minutes
  Target: < 10%
  Meaning: Unplanned gaps in the schedule

SAFETY_RATIO
  Formula: safety_minutes / total_shift_minutes
  Target: 2-5% (depends on policy)
  Meaning: Planned safety and meeting time

EFFECTIVE_AVAILABILITY
  Formula: (available_minutes - idle_minutes) / total_shift_minutes
  Target: > 85%
  Meaning: True productible time (excluding gaps)

ENGINE HOURS VALIDATION
  Check 1: Engine hours must increase if production occurred
  Check 2: No negative deltas
  Check 3: Deltas should align roughly with production time
  Alert: Rollover detection for deltas > 20 hours
"""
print(guide)
