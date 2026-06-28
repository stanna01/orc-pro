"""Tests for checklist persistence and API endpoints."""

from fastapi.testclient import TestClient


def test_create_and_read_checklist_form():
    """Verify checklist form creation and retrieval through the API."""
    from backend.app.main import create_app
    from backend.app.database import init_db

    init_db()  # ensure tables exist (engine is module-level; create_all is idempotent)
    app = create_app()

    payload = {
        "source_filename": "sample-loader.docx",
        "document_date": "2026-04-04",
        "shift": "night",
        "machine_number": "LOAD-001",
        "operator_name": "Juan Perez",
        "mine_number": "MINE-01",
        "permit_number": "PERMIT-123",
        "start_engine_hours": 1200.5,
        "end_engine_hours": 1212.3,
        "start_transmission_hours": 800.0,
        "end_transmission_hours": 810.2,
        "daily_checks": [
            {
                "row_index": 1,
                "check_item": "Engine oil",
                "status": "OK",
                "remarks": "No leaks",
                "duration_minutes": 15.0,
                "is_service_action": True,
            }
        ],
        "activity_entries": [
            {
                "row_index": 1,
                "activity_code_raw": "101",
                "activity_code_normalized": "101",
                "from_time_raw": "18:00",
                "to_time_raw": "19:30",
                "workplace_raw": "Pit A",
                "ore_waste_raw": "Ore",
                "loads_raw": "3",
                "remarks_raw": "Normal",
            }
        ],
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/checklists/", json=payload)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["shift"] == "night"
        assert data["machine_number"] == "LOAD-001"
        assert len(data["daily_checks"]) == 1
        assert len(data["activity_entries"]) == 1

        checklist_id = data["id"]
        get_response = client.get(f"/api/v1/checklists/{checklist_id}")
        assert get_response.status_code == 200
        details = get_response.json()
        assert details["checklist"]["id"] == checklist_id
        assert details["checklist"]["operator_name"] == "Juan Perez"
