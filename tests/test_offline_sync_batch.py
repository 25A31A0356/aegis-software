"""
Tests for Offline Sync Batch Gateway for Mobile & Web clients.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_offline_sync_batch_endpoint(async_client: AsyncClient):
    batch_payload = {
        "sos_events": [
            {
                "idempotency_key": "offline-batch-sos-01",
                "caller_name": "Offline User 1",
                "caller_phone": "+919988776655",
                "emergency_type": "flood_trapped",
                "severity": "CRITICAL",
                "short_message": "Queued while cell tower was down",
                "latitude": 20.2961,
                "longitude": 85.8245,
                "battery_percent": 45
            }
        ],
        "safe_events": [
            {
                "idempotency_key": "offline-batch-safe-01",
                "user_name": "Offline User 2",
                "user_phone": "+919988776644",
                "message": "Sheltered at community hall",
                "latitude": 20.2961,
                "longitude": 85.8245
            }
        ]
    }
    res = await async_client.post("/api/v1/sos/sync", json=batch_payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["synced_sos_count"] == 1
    assert data["synced_safe_count"] == 1
    assert len(data["sos_results"]) == 1
    assert data["sos_results"][0]["status"] == "SYNCED"
    assert len(data["safe_results"]) == 1
    assert data["safe_results"][0]["status"] == "SYNCED"

    # Resync identical batch -> must return ALREADY_SYNCED without duplicates
    res2 = await async_client.post("/api/v1/sos/sync", json=batch_payload)
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert data2["sos_results"][0]["status"] == "ALREADY_SYNCED"
    assert data2["safe_results"][0]["status"] == "ALREADY_SYNCED"