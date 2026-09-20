"""
AEGIS CENTRAL DATA GATEWAY - External Provider Failure & Degradation Tests
Simulates network timeouts, 500 errors, and offline provider states.
Verifies that Aegis Software handles failures gracefully without crashing or fabricating fake live data.
"""
import pytest
from unittest.mock import patch, AsyncMock
import httpx
from backend.app.providers.base import ProviderFetchResult
from backend.app.providers.adapters.open_meteo import OpenMeteoProvider
from backend.app.providers.adapters.usgs import USGSSeismologyProvider
from backend.app.providers.adapters.geographic import GeographicLocationProvider


@pytest.mark.asyncio
async def test_weather_provider_timeout_graceful_degradation(async_client):
    """Simulates Open-Meteo network timeout and verifies controlled fallback response."""
    with patch.object(
        OpenMeteoProvider,
        "fetch",
        new_callable=AsyncMock,
        return_value=ProviderFetchResult(success=False, error_message="Simulated connection timeout")
    ):
        response = await async_client.get("/api/v1/weather?lat=28.613&lng=77.209")
        assert response.status_code in [200, 503]
        data = response.json()
        if response.status_code == 200:
            assert data["success"] is True
            assert data["freshness"]["status"] == "stale"
        else:
            assert data["success"] is False
            assert "error" in data


@pytest.mark.asyncio
async def test_seismic_provider_500_error_handling(async_client):
    """Simulates USGS upstream 500 error and verifies that the gateway returns fallback catalog."""
    with patch.object(
        USGSSeismologyProvider,
        "fetch",
        new_callable=AsyncMock,
        return_value=ProviderFetchResult(success=False, status_code=500, error_message="Upstream USGS 500 Internal Error")
    ):
        response = await async_client.get("/api/v1/earthquakes?min_mag=3.0")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_forecast_provider_failure_fallback(async_client):
    """Simulates forecast provider failure and verifies structured atmospheric fallback."""
    # Mock httpx context manager inside forecast module
    mock_instance = AsyncMock()
    mock_instance.get = AsyncMock(side_effect=httpx.ConnectTimeout("External NWP server unreachable"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.api.v1.forecast.httpx.AsyncClient", return_value=mock_instance):
        response = await async_client.get("/api/v1/forecast?lat=13.082&lng=80.270&days=3")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert len(payload["daily"]) == 3
        assert payload["freshness_status"] == "stale"
        assert payload["source"] == "AEGIS Atmospheric Model Fallback"


@pytest.mark.asyncio
async def test_geographic_offline_centroid_fallback(async_client):
    """Verifies that location resolution uses built-in offline centroids when geocoding network is down."""
    with patch.object(
        GeographicLocationProvider,
        "fetch",
        new_callable=AsyncMock,
        return_value=ProviderFetchResult(success=False, error_message="Geocoding network unreachable")
    ):
        # Forward search with offline matching
        search_res = await async_client.get("/api/v1/location/search?query=Kolkata")
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["success"] is True
        assert len(search_data["data"]) >= 1
        assert "Kolkata" in search_data["data"][0]["name"]
        assert search_data["data"][0]["source"] == "AEGIS National Geographic Centroid Registry"

        # Reverse geocoding with offline Haversine matching
        rev_res = await async_client.get("/api/v1/location/reverse?lat=22.572&lng=88.363")
        assert rev_res.status_code == 200
        rev_data = rev_res.json()
        assert rev_data["success"] is True
        assert rev_data["data"]["name"] == "Kolkata"
        assert rev_data["data"]["state"] == "West Bengal"
