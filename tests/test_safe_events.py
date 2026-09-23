"""
Tests for Safe Check-in ("I AM SAFE") events and Auto SOS Resolution.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_declare_safe_and_auto_resolve_sos(async_client: AsyncClient):
    # 1. User triggers SOS distress
    user_id = "user_safe_test_01"
    sos_res = await async_client.post("/api/v1/sos", json={
        "caller_name": "Sunil Varma",
        "caller_phone": "+919811223344",
        "emergency_type": "cyclone_shelter",
        "severity": "HIGH",
        "latitude": 17.6868,
        "longitude": 83.2185,
        "requester_user_id": user_id,
        "idempotency_key": "test-sos-for-safe-resolve-001"
    })
    assert sos_res.status_code == 200
    sos_data = sos_res.json()["data"]
    sos_id = sos_data["id"]

    # 2. User subsequently declares "I AM SAFE"
    safe_res = await async_client.post("/api/v1/sos/safe", json={
        "user_name": "Sunil Varma",
        "user_phone": "+919811223344",
        "message": "Reached relief shelter safely. All family members accounted for.",
        "latitude": 17.6868,
        "longitude": 83.2185,
        "user_id": user_id,
        "idempotency_key": "test-safe-decl-001",
        "emergency_contacts": [
            {"name": "Ananya Varma", "phone": "+919811223355", "relationship": "Sister"}
        ]
    })
    assert safe_res.status_code == 200
    safe_data = safe_res.json()["data"]
    assert safe_data["status"] == "SAFE"
    assert safe_data["sos_id"] == sos_id
    assert safe_data["contacts_notified_count"] >= 1

    # 3. Verify original SOS is now marked RESOLVED
    sos_check = await async_client.get(f"/api/v1/sos/{sos_id}", headers={"X-Aegis-User-Id": user_id})
    assert sos_check.status_code == 200
    assert sos_check.json()["data"]["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_list_safe_events_and_filtering(async_client: AsyncClient):
    # Post a safe event
    await async_client.post("/api/v1/sos/safe", json={
        "user_name": "Priya Patel",
        "latitude": 23.0225,
        "longitude": 72.5714,
        "state": "Gujarat",
        "district": "Ahmedabad",
        "message": "Safe at home"
    })

    res = await async_client.get("/api/v1/sos/safe")
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1