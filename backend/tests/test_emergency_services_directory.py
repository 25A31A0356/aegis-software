"""
Tests for Emergency Services Directory & National Helplines.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_national_hotlines(async_client: AsyncClient):
    res = await async_client.get("/api/v1/emergency-services/national")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 8

    codes = [s["service_code"] for s in data]
    assert "IN_112_ERSS" in codes
    assert "IN_100_POLICE" in codes
    assert "IN_108_AMBULANCE" in codes
    assert "IN_101_FIRE" in codes
    assert "IN_1078_NDRF" in codes
    assert "IN_1091_WOMEN" in codes
    assert "IN_1098_CHILD" in codes
    assert "IN_1930_CYBER" in codes


@pytest.mark.asyncio
async def test_filter_emergency_services_by_category_and_search(async_client: AsyncClient):
    # Category filter: POLICE
    police_res = await async_client.get("/api/v1/emergency-services?category=POLICE")
    assert police_res.status_code == 200
    p_data = police_res.json()["data"]
    assert len(p_data) >= 1
    assert any("100" in p["primary_phone"] for p in p_data)

    # Search query: NDRF
    search_res = await async_client.get("/api/v1/emergency-services?search=NDRF")
    assert search_res.status_code == 200
    s_data = search_res.json()["data"]
    assert len(s_data) >= 1
    assert any("1078" in s["primary_phone"] for s in s_data)


@pytest.mark.asyncio
async def test_get_emergency_service_categories(async_client: AsyncClient):
    res = await async_client.get("/api/v1/emergency-services/categories")
    assert res.status_code == 200
    cats = res.json()["data"]
    assert len(cats) >= 7
    codes = [c["code"] for c in cats]
    assert "DISASTER_RESPONSE" in codes
    assert "POLICE" in codes
    assert "AMBULANCE" in codes