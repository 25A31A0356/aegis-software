"""
AEGIS CENTRAL DATA GATEWAY - Discovery, Auth & Client Verification Tests
Verifies /api/v1/discovery, /manifest, /api/v1/auth/register, /login, /me, and client-verify.
"""
import pytest
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_discovery_manifest_endpoint(async_client):
    """Verifies machine-readable discovery manifest returns non-secret endpoint catalogue."""
    response = await async_client.get("/api/v1/discovery")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    manifest = data["data"]
    assert manifest["service_name"] == "AEGIS Central Data Gateway"
    assert "WEATHER" in manifest["supported_data_categories"]
    assert "EARTHQUAKE" in manifest["supported_data_categories"]
    assert len(manifest["endpoints"]) >= 15

    # Test alias /manifest
    manifest_res = await async_client.get("/api/v1/manifest")
    assert manifest_res.status_code == 200


@pytest.mark.asyncio
async def test_user_registration_and_login_flow(async_client):
    """Verifies end-to-end citizen user registration, login, and JWT verification."""
    # 1. Register new user
    reg_payload = {
        "email": "citizen.user@aegis.gov.in",
        "password": "SecurePassword123!",
        "full_name": "Rohan Sharma",
        "role": "citizen"
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["success"] is True
    token = reg_data["data"]["access_token"]
    assert token is not None

    # 2. Login with registered user
    login_payload = {
        "email": "citizen.user@aegis.gov.in",
        "password": "SecurePassword123!"
    }
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["success"] is True
    login_token = login_data["data"]["access_token"]

    # 3. Access /auth/me with Bearer JWT
    me_res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["success"] is True
    assert me_data["data"]["email"] == "citizen.user@aegis.gov.in"
    assert me_data["data"]["full_name"] == "Rohan Sharma"


@pytest.mark.asyncio
async def test_client_credential_verification(async_client):
    """Verifies client validation endpoint for Web and App."""
    payload = {
        "client_type": "web",
        "client_key": settings.AEGIS_WEB_CLIENT_KEY
    }
    res = await async_client.post("/api/v1/auth/client-verify", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["data"]["valid"] is True
    assert data["data"]["access_tier"] == "STANDARD_GATEWAY_ACCESS"
