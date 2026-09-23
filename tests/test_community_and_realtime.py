"""
AEGIS UNIFIED DATA CORE - Community Reports, Real-Time Sync & Map Data Test Suite
Validates single source of truth, offline deduplication, activity feed, and GeoJSON map layers.
"""
import pytest
import uuid
from backend.app.realtime.manager import EventBroker


@pytest.mark.asyncio
async def test_create_and_query_community_report(async_client):
    """Validates citizen report submission and authoritative querying."""
    payload = {
        "category": "FLOOD",
        "title": "Severe Waterlogging Under Railway Underpass",
        "description": "Water level reaching 3 feet. Vehicles unable to cross.",
        "severity": "HIGH",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "location_name": "Minto Bridge Underpass",
        "city": "New Delhi",
        "state": "Delhi",
        "media_urls": ["https://aegis-storage.internal/media/flood_minto_1.jpg"]
    }
    res = await async_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    report = data["data"]
    assert report["category"] == "FLOOD"
    assert report["severity"] == "HIGH"
    assert report["status"] in ["ACTIVE", "SUBMITTED"]
    assert report["verification_status"] in ["UNVERIFIED_COMMUNITY", "UNVERIFIED"]
    assert report["is_verified"] is False
    assert report["source"] == "COMMUNITY"
    assert len(report["media_urls"]) == 1
    report_id = report["id"]

    # Fetch single report by ID
    get_res = await async_client.get(
        f"/api/v1/reports/{report_id}",
        headers={"X-Aegis-Client": "web", "X-Aegis-Client-Key": "test_web_client_key"}
    )
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["data"]["id"] == report_id
    assert get_data["data"]["city"] == "New Delhi"


@pytest.mark.asyncio
async def test_offline_sync_idempotency_deduplication(async_client):
    """Validates that re-submitting offline reports with the same idempotency_key returns identical record."""
    idempotency_key = f"offline_sync_{uuid.uuid4()}"
    payload = {
        "category": "BLOCKED_ROAD",
        "title": "Fallen Tree Blocking Highway Lane",
        "description": "Large banyan tree fallen across left lane of NH-44.",
        "severity": "MODERATE",
        "latitude": 28.7041,
        "longitude": 77.1025,
        "idempotency_key": idempotency_key
    }

    # First submission
    res1 = await async_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    assert res1.status_code == 200
    data1 = res1.json()["data"]

    # Duplicate submission (simulating mobile reconnect retry)
    res2 = await async_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    assert res2.status_code == 200
    data2 = res2.json()["data"]

    assert data1["id"] == data2["id"]
    assert data1["created_at"] == data2["created_at"]


@pytest.mark.asyncio
async def test_community_voting_and_verification_elevation(async_client):
    """Validates citizen upvoting and automatic promotion to VERIFIED_COMMUNITY."""
    # Create report
    c_res = await async_client.post(
        "/api/v1/reports",
        json={
            "category": "LANDSLIDE",
            "title": "Debris on Hill Road",
            "description": "Small rockslide blocking mountain curve.",
            "severity": "HIGH",
            "latitude": 30.3165,
            "longitude": 78.0322,
            "city": "Dehradun",
            "state": "Uttarakhand"
        },
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    report_id = c_res.json()["data"]["id"]

    # Vote 1
    v1 = await async_client.post(
        f"/api/v1/reports/{report_id}/vote",
        json={"voter_id": "device_user_alpha", "vote_type": "UPVOTE"},
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    assert v1.status_code == 200
    assert v1.json()["data"]["upvotes"] == 1
    assert v1.json()["data"]["is_verified"] is False

    # Vote 2 & Vote 3 (reaching threshold of 3)
    await async_client.post(
        f"/api/v1/reports/{report_id}/vote",
        json={"voter_id": "device_user_beta", "vote_type": "UPVOTE"},
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    v3 = await async_client.post(
        f"/api/v1/reports/{report_id}/vote",
        json={"voter_id": "device_user_gamma", "vote_type": "UPVOTE"},
        headers={"X-Aegis-Client": "app", "X-Aegis-Client-Key": "test_app_client_key"}
    )
    v3_data = v3.json()["data"]
    assert v3_data["upvotes"] == 3
    assert v3_data["is_verified"] is True
    assert v3_data["verification_status"] in ["VERIFIED_COMMUNITY", "VERIFIED"]


@pytest.mark.asyncio
async def test_unified_activity_feed(async_client):
    """Validates /api/v1/activity endpoint filtering and schema compliance."""
    res = await async_client.get(
        "/api/v1/activity?limit=20",
        headers={"X-Aegis-Client": "web", "X-Aegis-Client-Key": "test_web_client_key"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_unified_map_data_geojson(async_client):
    """Validates /api/v1/map-data GeoJSON FeatureCollection across GIS layers."""
    res = await async_client.get(
        "/api/v1/map-data?layers=all",
        headers={"X-Aegis-Client": "web", "X-Aegis-Client-Key": "test_web_client_key"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    map_fc = body["data"]
    assert map_fc["type"] == "FeatureCollection"
    assert "features" in map_fc
    assert "layer_summary" in map_fc
    assert isinstance(map_fc["features"], list)


@pytest.mark.asyncio
async def test_event_broker_sanitization():
    """Validates that EventBroker strictly sanitizes private user information before streaming."""
    raw_payload = {
        "report_id": "rep-12345",
        "title": "Road flooded",
        "caller_phone": "+91-9876543210",
        "email": "citizen@example.com",
        "hashed_password": "supersecretpassword",
        "user_id": "usr-9999",
        "severity": "HIGH"
    }
    clean = EventBroker.sanitize_payload(raw_payload)
    assert "caller_phone" not in clean
    assert "email" not in clean
    assert "hashed_password" not in clean
    assert "user_id" not in clean
    assert clean["title"] == "Road flooded"
    assert clean["severity"] == "HIGH"
