"""
Tests for Privacy Preserving Location Redaction and RBAC.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_public_user_receives_redacted_sos(async_client: AsyncClient):
    # Create an SOS
    sos_res = await async_client.post("/api/v1/sos", json={
        "caller_name": "Private Citizen",
        "caller_phone": "+919876543210",
        "emergency_type": "medical",
        "severity": "CRITICAL",
        "latitude": 18.5204321,
        "longitude": 73.8567432,
        "accuracy_meters": 5.0,
        "address": "Flat 402, High-Rise Tower, Pune",
        "idempotency_key": "test-privacy-sos-001"
    })
    assert sos_res.status_code == 200
    sos_id = sos_res.json()["data"]["id"]

    # Public viewer (unauthorized) retrieves the SOS
    pub_res = await async_client.get(f"/api/v1/sos/{sos_id}")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()["data"]

    # Exact phone must be masked
    assert "*****" in pub_data["caller_phone_masked"]
    # Exact caller name should be generic for public
    assert pub_data["caller_name"] == "Citizen in Distress"
    # Coordinates should be rounded to 2 decimal places for privacy
    assert pub_data["latitude"] == round(18.5204321, 2)
    assert pub_data["longitude"] == round(73.8567432, 2)
    assert pub_data["is_authorized_view"] is False


@pytest.mark.asyncio
async def test_sos_map_feed_returns_redacted_markers(async_client: AsyncClient):
    # Ensure at least one SOS exists
    await async_client.post("/api/v1/sos", json={
        "caller_name": "Citizen Map Test",
        "caller_phone": "+919876543210",
        "emergency_type": "general",
        "severity": "HIGH",
        "latitude": 19.0760,
        "longitude": 72.8777
    })

    res = await async_client.get("/api/v1/sos/map/feed")
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    for item in data:
        assert item["is_authorized_view"] is False
        assert "*****" in item["caller_phone_masked"]