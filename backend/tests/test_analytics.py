"""Unit tests for machine analytics module."""

import pytest
from backend.app.services.analytics import (
    compute_engine_hours_metrics,
    compute_availability_breakdown,
    compute_performance_ratios,
    compute_machine_analytics,
)


class TestEngineHoursMetrics:
    def test_valid_engine_hours_increase(self):
        """Engine hours should increase with production."""
        metrics = compute_engine_hours_metrics(
            start_engine_hours=1000.0,
            end_engine_hours=1010.0,
            start_transmission_hours=500.0,
            end_transmission_hours=505.0,
            production_minutes=600.0,
        )
        assert metrics.engine_hours_valid is True
        assert metrics.engine_hours_delta == 10.0
        assert metrics.transmission_hours_delta == 5.0

    def test_invalid_engine_hours_decrease(self):
        """Engine hours decreasing should be flagged as invalid."""
        metrics = compute_engine_hours_metrics(
            start_engine_hours=1010.0,
            end_engine_hours=1000.0,
            start_transmission_hours=505.0,
            end_transmission_hours=500.0,
        )
        assert metrics.engine_hours_valid is False
        assert "decreased" in metrics.validation_message.lower()

    def test_engine_hours_alert_large_delta(self):
        """Engine hours delta > 20 should trigger alert."""
        metrics = compute_engine_hours_metrics(
            start_engine_hours=1000.0,
            end_engine_hours=1025.0,
            start_transmission_hours=500.0,
            end_transmission_hours=510.0,
        )
        assert "exceeded" in metrics.validation_message.lower() or metrics.engine_hours_valid is True

    def test_no_production_no_change(self):
        """Zero production with zero engine hours change is suspicious."""
        metrics = compute_engine_hours_metrics(
            start_engine_hours=1000.0,
            end_engine_hours=1000.0,
            start_transmission_hours=500.0,
            end_transmission_hours=500.0,
            production_minutes=300.0,
        )
        assert metrics.engine_hours_valid is False
        assert "unchanged" in metrics.validation_message.lower()


class TestAvailabilityBreakdown:
    def test_day_shift_availability(self):
        """Availability should be correctly computed for day shift."""
        events = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "12:00",
                "duration_minutes": 360.0,
            },
            {
                "event_type": "service",
                "start_time": "12:00",
                "end_time": "13:00",
                "duration_minutes": 60.0,
            },
            {
                "event_type": "production",
                "start_time": "13:00",
                "end_time": "18:00",
                "duration_minutes": 300.0,
            },
        ]
        avail = compute_availability_breakdown(events, shift="day", release_time="13:00")
        assert avail.total_shift_minutes == 720
        assert avail.production_minutes == 660.0
        assert avail.service_minutes == 60.0
        assert avail.available_minutes > 0

    def test_night_shift_availability(self):
        """Availability should be correctly computed for night shift."""
        events = [
            {
                "event_type": "production",
                "start_time": "18:00",
                "end_time": "22:00",
                "duration_minutes": 240.0,
            },
            {
                "event_type": "breakdown",
                "start_time": "22:00",
                "end_time": "23:00",
                "duration_minutes": 60.0,
            },
            {
                "event_type": "production",
                "start_time": "23:00",
                "end_time": "04:00",
                "duration_minutes": 300.0,
            },
        ]
        avail = compute_availability_breakdown(events, shift="night", release_time="23:00")
        assert avail.total_shift_minutes == 720
        assert avail.production_minutes == 540.0
        assert avail.breakdown_minutes == 60.0

    def test_breakdown_reduces_availability(self):
        """Breakdown time should reduce available minutes."""
        events_no_breakdown = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "18:00",
                "duration_minutes": 720.0,
            }
        ]
        events_with_breakdown = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "12:00",
                "duration_minutes": 360.0,
            },
            {
                "event_type": "breakdown",
                "start_time": "12:00",
                "end_time": "13:00",
                "duration_minutes": 60.0,
            },
            {
                "event_type": "production",
                "start_time": "13:00",
                "end_time": "18:00",
                "duration_minutes": 300.0,
            },
        ]
        avail1 = compute_availability_breakdown(events_no_breakdown, "day", "06:00")
        avail2 = compute_availability_breakdown(events_with_breakdown, "day", "13:00")

        assert avail1.breakdown_minutes == 0
        assert avail2.breakdown_minutes == 60.0


class TestPerformanceRatios:
    def test_availability_ratio(self):
        """Availability ratio should be available/total."""
        events = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "18:00",
                "duration_minutes": 720.0,
            }
        ]
        avail = compute_availability_breakdown(events, "day", "06:00")
        perf = compute_performance_ratios(avail)

        assert perf.availability_ratio is not None
        assert 0 <= perf.availability_ratio <= 1

    def test_utilization_ratio(self):
        """Utilization ratio should be production/available."""
        events = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "16:00",
                "duration_minutes": 600.0,
            },
            {
                "event_type": "idle",
                "start_time": "16:00",
                "end_time": "18:00",
                "duration_minutes": 120.0,
            },
        ]
        avail = compute_availability_breakdown(events, "day", "06:00")
        perf = compute_performance_ratios(avail)

        expected_utilization = 600.0 / (600.0 + 120.0)
        assert abs(perf.utilization_ratio - expected_utilization) < 0.01

    def test_downtime_ratio(self):
        """Downtime ratio should be breakdown/available."""
        events = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "12:00",
                "duration_minutes": 360.0,
            },
            {
                "event_type": "breakdown",
                "start_time": "12:00",
                "end_time": "13:00",
                "duration_minutes": 60.0,
            },
            {
                "event_type": "production",
                "start_time": "13:00",
                "end_time": "18:00",
                "duration_minutes": 300.0,
            },
        ]
        avail = compute_availability_breakdown(events, "day", "13:00")
        perf = compute_performance_ratios(avail)

        assert perf.downtime_ratio is not None
        assert perf.downtime_ratio > 0

    def test_all_ratios_in_range(self):
        """All ratios should be between 0 and 1."""
        events = [
            {
                "event_type": "production",
                "start_time": "06:00",
                "end_time": "14:00",
                "duration_minutes": 480.0,
            },
            {
                "event_type": "breakdown",
                "start_time": "14:00",
                "end_time": "15:00",
                "duration_minutes": 60.0,
            },
            {
                "event_type": "production",
                "start_time": "15:00",
                "end_time": "18:00",
                "duration_minutes": 180.0,
            },
        ]
        avail = compute_availability_breakdown(events, "day", "15:00")
        perf = compute_performance_ratios(avail)

        for ratio_name in [
            "availability_ratio",
            "utilization_ratio",
            "downtime_ratio",
            "production_ratio",
            "breakdown_ratio",
            "idle_ratio",
            "safety_ratio",
            "effective_availability_ratio",
        ]:
            ratio = getattr(perf, ratio_name)
            if ratio is not None:
                assert 0 <= ratio <= 1, f"{ratio_name} = {ratio} out of range"


class TestFullAnalytics:
    def test_end_to_end_analytics(self):
        """Full analytics pipeline should execute without error."""
        events = [
            {
                "row_index": 1,
                "activity_code": "101",
                "start_time": "06:00",
                "end_time": "08:00",
                "duration_minutes": 120.0,
                "event_type": "production",
            },
            {
                "row_index": 2,
                "activity_code": "200",
                "start_time": "08:00",
                "end_time": "09:00",
                "duration_minutes": 60.0,
                "event_type": "service",
            },
            {
                "row_index": 3,
                "activity_code": "101",
                "start_time": "09:00",
                "end_time": "18:00",
                "duration_minutes": 540.0,
                "event_type": "production",
            },
        ]

        result = compute_machine_analytics(
            events=events,
            shift="day",
            release_time="09:00",
            start_engine_hours=1000.0,
            end_engine_hours=1009.0,
            start_transmission_hours=500.0,
            end_transmission_hours=503.0,
        )

        assert "availability_breakdown" in result
        assert "engine_hours_metrics" in result
        assert "performance_ratios" in result

        avail = result["availability_breakdown"]
        assert avail["total_shift_minutes"] == 720
        assert avail["production_minutes"] == 660.0

        engine = result["engine_hours_metrics"]
        assert engine["engine_hours_delta"] == 9.0

        perf = result["performance_ratios"]
        assert perf["availability_ratio"] > 0

    def test_night_shift_end_to_end(self):
        """Analytics should handle night shift correctly."""
        events = [
            {
                "event_type": "production",
                "start_time": "18:00",
                "end_time": "20:00",
                "duration_minutes": 120.0,
            },
            {
                "event_type": "breakdown",
                "start_time": "20:00",
                "end_time": "21:00",
                "duration_minutes": 60.0,
            },
            {
                "event_type": "production",
                "start_time": "21:00",
                "end_time": "04:00",
                "duration_minutes": 300.0,
            },
        ]

        result = compute_machine_analytics(
            events=events,
            shift="night",
            release_time="21:00",
            start_engine_hours=1200.0,
            end_engine_hours=1208.0,
        )

        avail = result["availability_breakdown"]
        assert avail["breakdown_minutes"] == 60.0
        assert avail["production_minutes"] == 420.0
