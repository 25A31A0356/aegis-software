"""
AEGIS UNIFIED DATA CORE - Tests for Mobile App & SOS Endpoints
Validates integration with https://github.com/25A31A0356/aegis-alert
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
async def test_mobile_sync_bundle(async_client: AsyncClient):
    res = await async_client.get("/api/v1/mobile/sync?lat=28.6139&lon=77.2090&radius_km=100")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "nearby_alerts_count" in data
    assert "threat_level" in data
    assert "emergency_helplines" in data
    assert data["emergency_helplines"]["National Emergency Number"] == "112"


@pytest.mark.asyncio
async def test_create_and_list_sos_distress_beacon(async_client: AsyncClient):
    # 1. Post SOS
    sos_payload = {
        "caller_name": "Test Citizen",
        "caller_phone": "+919876543210",
        "emergency_type": "flood_trapped",
        "severity": "CRITICAL",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "address": "Near Yamuna Bank, Ring Road",
        "city": "New Delhi",
        "state": "Delhi",
        "battery_percent": 82,
        "medical_notes": "Asthma patient, needs urgent boat rescue",
        "casualties_count": 3
    }
    res = await async_client.post("/api/v1/sos", json=sos_payload)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["success"] is True
    created = json_data["data"]
    assert created["emergency_type"] == "flood_trapped"
    assert created["caller_phone_masked"].endswith("10")
    assert created["status"] == "PENDING_TRIAGE"

    # 2. List SOS
    list_res = await async_client.get("/api/v1/sos")
    assert list_res.status_code == 200
    list_json = list_res.json()
    assert list_json["success"] is True
    assert len(list_json["data"]) >= 1


@pytest.mark.asyncio
async def test_create_and_list_incident_report(async_client: AsyncClient):
    report_payload = {
        "hazard_type": "FLOOD",
        "title": "Waterlogging on Outer Ring Road",
        "description": "Knee-deep water accumulation causing heavy traffic gridlock",
        "severity": "medium",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "city": "New Delhi",
        "state": "Delhi",
        "media_urls": ["https://cdn.example.org/photo1.jpg"]
    }
    res = await async_client.post("/api/v1/reports", json=report_payload)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["success"] is True
    assert json_data["data"]["hazard_type"] == "FLOOD"

    # List reports
    list_res = await async_client.get("/api/v1/reports")
    assert list_res.status_code == 200
    assert list_res.json()["success"] is True
