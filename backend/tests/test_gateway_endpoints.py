"""
AEGIS UNIFIED DATA CORE - Gateway Endpoints & Client Contract Tests
Verifies /health, /forecast, /location, /status, /hazards/nearby, provider degradation, and client isolation.
"""
import pytest
from datetime import datetime, timezone
from backend.app.database.models import NormalizedObservation, DataSource


@pytest.mark.asyncio
async def test_top_level_health(async_client):
    """Verifies top-level /health endpoint returns operational system status."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "system_status" in data["data"]
    assert data["data"]["security_posture"] == "HARDENED"


@pytest.mark.asyncio
async def test_forecast_endpoint(async_client):
    """Verifies /api/v1/forecast returns multi-day and hourly forecast telemetry."""
    response = await async_client.get("/api/v1/forecast?lat=19.076&lng=72.877&days=5")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    payload = data["data"]
    assert "daily" in payload
    assert "hourly" in payload
    assert len(payload["daily"]) == 5
    assert len(payload["hourly"]) <= 24
    assert payload["coordinates"] == [19.076, 72.877]


@pytest.mark.asyncio
async def test_location_search_and_reverse(async_client):
    """Verifies /api/v1/location forward geocoding and reverse geocoding."""
    # 1. Forward Geocoding
    search_res = await async_client.get("/api/v1/location/search?query=Mumbai")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["success"] is True
    assert len(search_data["data"]) >= 1
    assert "Mumbai" in search_data["data"][0]["name"]

    # 2. Reverse Geocoding
    rev_res = await async_client.get("/api/v1/location/reverse?lat=19.076&lng=72.877")
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["success"] is True
    assert "district" in rev_data["data"]
    assert "state" in rev_data["data"]

    # 3. Combined /location route
    comb_res = await async_client.get("/api/v1/location?query=Delhi")
    assert comb_res.status_code == 200
    assert comb_res.json()["success"] is True


@pytest.mark.asyncio
async def test_gateway_status_matrix(async_client):
    """Verifies /api/v1/status lists all 8 official provider adapters with health metrics."""
    response = await async_client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    payload = data["data"]
    assert payload["platform_status"] in ["OPERATIONAL", "DEGRADED"]
    assert payload["total_providers_count"] == 8
    provider_codes = [p["provider_code"] for p in payload["providers"]]
    assert "open_meteo" in provider_codes
    assert "usgs" in provider_codes
    assert "nasa_firms" in provider_codes
    assert "imd" in provider_codes
    assert "cwc" in provider_codes
    assert "incois" in provider_codes
    assert "cpcb" in provider_codes
    assert "geographic" in provider_codes


@pytest.mark.asyncio
async def test_hazards_nearby_spatial_query(async_client, test_db):
    """Verifies /api/v1/hazards/nearby calculates distance, bearing, and proximity order."""
    now = datetime.now(timezone.utc)
    obs1 = NormalizedObservation(
        id="TEST-HAZ-NEAR-1",
        data_source_id="TEST_SOURCE",
        hazard_type="FLOOD",
        latitude=19.100,
        longitude=72.890,
        location_name="Nearby Test Station",
        state_name="Maharashtra",
        district_name="Mumbai Suburban",
        observed_at=now,
        received_at=now,
        severity="warning",
        risk_level="HIGH",
        confidence=0.9,
        source_authority="CWC Flood Warning",
        measurements={"water_level_m": 45.2}
    )
    test_db.add(obs1)
    await test_db.commit()

    response = await async_client.get("/api/v1/hazards/nearby?lat=19.076&lng=72.877&radius_km=25")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1
    item = data["data"][0]
    assert "distance_km" in item
    assert item["distance_km"] <= 25.0
    assert "bearing_degrees" in item
    assert item["type"] == "flood"
    assert item["severity"] == "HIGH"
    assert item["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_client_identification_headers(async_client):
    """Verifies X-Aegis-Client header context handling for Web and App."""
    # Web client request
    res_web = await async_client.get("/api/v1/weather?lat=19.076&lng=72.877", headers={"X-Aegis-Client": "web"})
    assert res_web.status_code in [200, 503]

    # Mobile app client request
    res_app = await async_client.get("/api/v1/mobile/sync?lat=19.076&lon=72.877&radius_km=50", headers={"X-Aegis-Client": "app"})
    assert res_app.status_code == 200
    app_data = res_app.json()
    assert app_data["success"] is True
    assert "emergency_helplines" in app_data["data"]
