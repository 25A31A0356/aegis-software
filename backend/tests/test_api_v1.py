"""
AEGIS UNIFIED DATA CORE - Integration API Tests
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_root(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert "AEGIS UNIFIED DATA CORE" in data["service"]


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["data"]["system_status"] in ("HEALTHY", "DEGRADED")
    assert json_data["data"]["security_posture"] == "HARDENED"


@pytest.mark.asyncio
async def test_weather_endpoint(async_client: AsyncClient, test_db):
    from datetime import datetime, timezone
    from backend.app.database.models import NormalizedObservation
    # Seed a normalized weather observation
    seed_obs = NormalizedObservation(
        id="test-seed-weather-1",
        hazard_type="WEATHER",
        latitude=19.0760,
        longitude=72.8777,
        location_name="Mumbai Telemetry Station",
        state_name="Maharashtra",
        observed_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        severity="moderate",
        risk_level="MODERATE",
        confidence=0.95,
        data_type="official_observation",
        source_authority="Open-Meteo & IMD Telemetry Network",
        processing_version="1.0.0",
        measurements={
            "temperature_c": 31.0,
            "apparent_temperature_c": 34.0,
            "humidity_percent": 75.0,
            "wind_speed_kmh": 18.0,
            "precipitation_mm": 2.5,
            "pressure_hpa": 1008.0,
            "uv_index": 6.0
        }
    )
    test_db.add(seed_obs)
    await test_db.commit()

    response = await async_client.get("/api/v1/weather?lat=19.0760&lng=72.8777")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "temperature" in data
    assert "humidity" in data
    assert "wind_speed" in data
    assert json_data["freshness"]["status"] in ("fresh", "stale")


@pytest.mark.asyncio
async def test_hazards_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/hazards")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert isinstance(json_data["data"], list)


@pytest.mark.asyncio
async def test_earthquakes_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/earthquakes?min_mag=3.0")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert isinstance(json_data["data"], list)


@pytest.mark.asyncio
async def test_admin_source_crud_and_ssrf(async_client: AsyncClient, admin_headers: dict):
    # 1. Test creating an invalid SSRF source (should fail)
    bad_payload = {
        "name": "Internal Exploiter",
        "provider_code": "custom_http",
        "category": "WEATHER",
        "base_url": "http://127.0.0.1:8000",
        "endpoint": "/secrets"
    }
    res_bad = await async_client.post("/api/v1/sources", json=bad_payload, headers=admin_headers)
    assert res_bad.status_code == 400
    assert "SSRF" in res_bad.json().get("detail", "")

    # 2. Test creating a valid external source
    good_payload = {
        "name": "Official Open-Meteo Gateway",
        "provider_code": "open_meteo",
        "category": "WEATHER",
        "base_url": "https://api.open-meteo.com/v1",
        "endpoint": "/forecast",
        "api_key_or_token": "TEST_SECRET_KEY_12345",
        "update_frequency_minutes": 5,
        "is_enabled": True
    }
    res_good = await async_client.post("/api/v1/sources", json=good_payload, headers=admin_headers)
    assert res_good.status_code == 201
    created = res_good.json()["data"]
    source_id = created["id"]
    assert created["name"] == "Official Open-Meteo Gateway"
    # Secret must be masked!
    assert "TEST_SECRET" not in str(created.get("masked_api_key", ""))
    assert created.get("masked_api_key", "").endswith("2345")

    # 3. List sources
    res_list = await async_client.get("/api/v1/sources", headers=admin_headers)
    assert res_list.status_code == 200
    sources = res_list.json()["data"]
    assert len(sources) >= 1

    # 4. Trigger on-demand ingestion
    res_trigger = await async_client.post(f"/api/v1/sources/{source_id}/trigger", headers=admin_headers)
    assert res_trigger.status_code == 200

    # 5. Delete source
    res_del = await async_client.delete(f"/api/v1/sources/{source_id}", headers=admin_headers)
    assert res_del.status_code == 200
