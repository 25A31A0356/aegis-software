"""
Tests for SOS Incident Lifecycle, Deduplication, and Offline Sync.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sos_creation_and_idempotency(async_client: AsyncClient):
    # Create SOS with idempotency key
    payload = {
        "caller_name": "Ravi Kumar",
        "caller_phone": "+919876543210",
        "emergency_type": "flood_trapped",
        "severity": "CRITICAL",
        "short_message": "Water level rising rapidly on ground floor",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "idempotency_key": "test-idem-sos-001",
        "device_id": "device-ravi-001"
    }
    res1 = await async_client.post("/api/v1/sos", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()["data"]
    assert data1["emergency_type"] == "flood_trapped"
    assert data1["severity"] == "CRITICAL"
    assert "Tamil" in data1["state"]
    first_id = data1["id"]

    # Resubmit with same idempotency key -> must return identical record without duplicates
    res2 = await async_client.post("/api/v1/sos", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert data2["id"] == first_id


@pytest.mark.asyncio
async def test_offline_reverse_geocoding_on_sos(async_client: AsyncClient):
    # Submit SOS without state or district -> should auto reverse-geocode to nearest centroid
    payload = {
        "caller_name": "Pooja Sharma",
        "caller_phone": "+919123456789",
        "emergency_type": "medical",
        "severity": "HIGH",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "idempotency_key": "test-idem-sos-delhi-002"
    }
    res = await async_client.post("/api/v1/sos", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "Delhi" in data["state"] or "New Delhi" in data["city"] or "Delhi" in data["district"]