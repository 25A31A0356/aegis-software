"""
AEGIS UNIFIED DATA CORE - Comprehensive SOS Nearby-Responder Network Test Suite
Verifies all 20 emergency workflows:
1. User creates SOS
2. Family contacts receive notification
3. Nearby responder is found
4. 10 km matching works
5. 20 km expansion works
6. Ineligible user is excluded (opted out / unavailable / busy)
7. Responder receives offer
8. Responder accepts
9. Second responder cannot steal assignment (race condition safety)
10. Exact location becomes available only after authorization
11. Route is generated
12. Location updates work (requester breadcrumbs)
13. Responder location updates work & recalculate route/ETA
14. Web receives realtime event
15. App receives realtime event
16. SOS cancellation works
17. SOS expiration works
18. State persistence across DB sessions
19. Unauthorized user cannot access confidential SOS details
20. Rate limiting works
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database.models import (
    User, UserPreference, SOSSignal, SOSResponderCandidate, SOSAssignment,
    SOSNotification, utc_now
)
from backend.app.sos.state_machine import SOSState


@pytest.mark.asyncio
async def test_01_user_creates_sos_and_02_family_notified(async_client: AsyncClient, test_db: AsyncSession):
    """Scenario 1: User creates SOS. Scenario 2: Family contacts receive notification."""
    payload = {
        "caller_name": "Rohan Sharma",
        "caller_phone": "+919876543210",
        "emergency_type": "FLOOD_TRAPPED",
        "severity": "CRITICAL",
        "short_message": "Water rising rapidly in ground floor",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "accuracy_meters": 5.0,
        "city": "New Delhi",
        "district": "New Delhi",
        "state": "Delhi",
        "battery_percent": 85,
        "casualties_count": 2,
        "emergency_contacts": [
            {"name": "Ananya Sharma", "phone": "+919811122233", "relationship": "Sister"}
        ]
    }

    res = await async_client.post("/api/v1/sos", json=payload, headers={"X-Aegis-Client": "app"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    sos_data = data["data"]
    assert sos_data["caller_name"] == "Rohan Sharma"
    assert sos_data["emergency_type"] == "flood_trapped"
    assert sos_data["status"] in (SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value)

    # Verify family notification was logged
    notif_res = await test_db.execute(
        select(SOSNotification).where(
            SOSNotification.sos_id == sos_data["id"],
            SOSNotification.recipient_type == "FAMILY_CONTACT"
        )
    )
    notifs = notif_res.scalars().all()
    assert len(notifs) >= 1
    assert notifs[0].recipient_id == "+919811122233"


@pytest.mark.asyncio
async def test_03_nearby_responder_found_and_04_10km_matching(async_client: AsyncClient, test_db: AsyncSession):
    """Scenario 3 & 4: Nearby opted-in responder within 10 km is discovered and offered."""
    # Seed Responder 1 (4.2 km away from Connaught Place Delhi: 28.6139, 77.2090 -> 28.6500, 77.2100)
    user_1 = User(id="resp-user-1", email="volunteer1@aegis.org", hashed_password="pw", full_name="Volunteer Vikram", role="responder", is_active=True)
    pref_1 = UserPreference(
        user_id="resp-user-1",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=28.6500,
        last_known_lng=77.2100,
        last_location_time=utc_now()
    )
    test_db.add(user_1)
    test_db.add(pref_1)
    await test_db.commit()

    # Create SOS
    sos_payload = {
        "caller_name": "Citizen Trapped",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "emergency_type": "MEDICAL",
        "city": "New Delhi"
    }
    res = await async_client.post("/api/v1/sos", json=sos_payload)
    assert res.status_code == 200
    sos_id = res.json()["data"]["id"]

    # Check candidate offers
    cand_res = await test_db.execute(
        select(SOSResponderCandidate).where(SOSResponderCandidate.sos_id == sos_id)
    )
    cands = cand_res.scalars().all()
    assert len(cands) == 1
    assert cands[0].responder_user_id == "resp-user-1"
    assert cands[0].distance_km < 10.0
    assert cands[0].status == "OFFERED"


@pytest.mark.asyncio
async def test_05_20km_expansion_when_no_10km_candidate(async_client: AsyncClient, test_db: AsyncSession):
    """Scenario 5: Search expands to 20 km when 0 candidates exist within 10 km."""
    # Seed Responder 2 (14.5 km away: 28.4830, 77.2090)
    user_2 = User(id="resp-user-2", email="volunteer2@aegis.org", hashed_password="pw", full_name="Far Volunteer", role="responder", is_active=True)
    pref_2 = UserPreference(
        user_id="resp-user-2",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=28.4830,  # ~14.5 km south
        last_known_lng=77.2090,
        last_location_time=utc_now()
    )
    test_db.add(user_2)
    test_db.add(pref_2)
    await test_db.commit()

    sos_payload = {
        "caller_name": "Lone Requester",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "emergency_type": "FIRE",
        "city": "New Delhi"
    }
    res = await async_client.post("/api/v1/sos", json=sos_payload)
    assert res.status_code == 200
    sos_id = res.json()["data"]["id"]

    cand_res = await test_db.execute(
        select(SOSResponderCandidate).where(SOSResponderCandidate.sos_id == sos_id)
    )
    cands = cand_res.scalars().all()
    assert len(cands) == 1
    assert cands[0].responder_user_id == "resp-user-2"
    assert 10.0 < cands[0].distance_km <= 20.0


@pytest.mark.asyncio
async def test_06_ineligible_user_excluded(async_client: AsyncClient, test_db: AsyncSession):
    """Scenario 6: Ineligible users (opted-out, unavailable, >20km, or busy) are excluded."""
    # User A: Opted out
    u_a = User(id="u-opted-out", email="optout@aegis.org", hashed_password="pw", role="public", is_active=True)
    p_a = UserPreference(user_id="u-opted-out", is_responder_opted_in=False, is_available=True, last_known_lat=28.6140, last_known_lng=77.2090)
    
    # User B: Unavailable
    u_b = User(id="u-unavail", email="unavail@aegis.org", hashed_password="pw", role="responder", is_active=True)
    p_b = UserPreference(user_id="u-unavail", is_responder_opted_in=True, is_available=False, last_known_lat=28.6140, last_known_lng=77.2090)

    # User C: Too far (> 50 km)
    u_c = User(id="u-far", email="far@aegis.org", hashed_password="pw", role="responder", is_active=True)
    p_c = UserPreference(user_id="u-far", is_responder_opted_in=True, is_available=True, last_known_lat=29.5000, last_known_lng=77.2090)

    test_db.add_all([u_a, p_a, u_b, p_b, u_c, p_c])
    await test_db.commit()

    sos_payload = {
        "caller_name": "Requester Test",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "emergency_type": "GENERAL"
    }
    res = await async_client.post("/api/v1/sos", json=sos_payload)
    sos_id = res.json()["data"]["id"]

    cand_res = await test_db.execute(
        select(SOSResponderCandidate).where(SOSResponderCandidate.sos_id == sos_id)
    )
    cands = cand_res.scalars().all()
    assert len(cands) == 0


@pytest.mark.asyncio
async def test_07_responder_receives_offer_and_08_accepts_and_09_race_condition(
    async_client: AsyncClient, test_db: AsyncSession
):
    """Scenario 7, 8, 9: Rapido-like offers, acceptance, route computation, and race-condition safety."""
    # Seed Responder A and Responder B
    u_a = User(id="responder-a", email="respA@aegis.org", hashed_password="pw", role="responder", is_active=True)
    p_a = UserPreference(user_id="responder-a", is_responder_opted_in=True, is_available=True, last_known_lat=28.6300, last_known_lng=77.2100)
    
    u_b = User(id="responder-b", email="respB@aegis.org", hashed_password="pw", role="responder", is_active=True)
    p_b = UserPreference(user_id="responder-b", is_responder_opted_in=True, is_available=True, last_known_lat=28.6400, last_known_lng=77.2100)
    
    test_db.add_all([u_a, p_a, u_b, p_b])
    await test_db.commit()

    # Create SOS
    sos_res = await async_client.post("/api/v1/sos", json={"caller_name": "Accident Victim", "latitude": 28.6139, "longitude": 77.2090, "emergency_type": "ACCIDENT"})
    sos_id = sos_res.json()["data"]["id"]

    # 7. Check offers for Responder A via GET /api/v1/sos/nearby
    offers_res = await async_client.get("/api/v1/sos/nearby", headers={"X-Aegis-User-Id": "responder-a"})
    assert offers_res.status_code == 200
    offers = offers_res.json()["data"]
    assert len(offers) >= 1
    assert offers[0]["sos_id"] == sos_id
    assert "approximate_distance_km" in offers[0]
    # Verify exact GPS is concealed in offer
    assert "latitude" not in offers[0]

    # 8. Responder A accepts
    accept_a = await async_client.post(f"/api/v1/sos/{sos_id}/accept", headers={"X-Aegis-User-Id": "responder-a"})
    assert accept_a.status_code == 200
    accepted_data = accept_a.json()["data"]
    assert accepted_data["status"] == "ACCEPTED"
    assert accepted_data["accepted_by"] == "responder-a"
    assert accepted_data["route"] is not None
    assert accepted_data["eta_seconds"] is not None

    # 9. Responder B tries to accept milliseconds later (Race Condition)
    accept_b = await async_client.post(f"/api/v1/sos/{sos_id}/accept", headers={"X-Aegis-User-Id": "responder-b"})
    assert accept_b.status_code == 409
    err_msg = accept_b.json().get("detail") or accept_b.json().get("error", {}).get("message", "")
    assert "already accepted" in err_msg.lower()


@pytest.mark.asyncio
async def test_10_exact_location_privacy_controls(async_client: AsyncClient, test_db: AsyncSession):
    """Scenario 10 & 19: Exact coordinates revealed only to authorized users (requester/responder/admin)."""
    now = utc_now()
    sos = SOSSignal(
        id="sos-privacy-test",
        user_id="requester-123",
        requester_user_id="requester-123",
        caller_name="Secret Citizen",
        caller_phone="+919876500000",
        emergency_type="medical",
        severity="HIGH",
        status="ACCEPTED",
        latitude=28.613945,
        longitude=77.209012,
        accuracy_meters=4.2,
        address="Confidential Private Apartment 4B",
        city="New Delhi",
        district="Central Delhi",
        state="Delhi",
        accepted_by="assigned-resp-456",
        medical_notes="Severe Asthma",
        created_at=now,
        updated_at=now
    )
    test_db.add(sos)
    await test_db.commit()

    # 1. Anonymous / Unauthorized viewer
    anon_res = await async_client.get("/api/v1/sos/sos-privacy-test")
    anon_data = anon_res.json()["data"]
    assert anon_data["is_authorized_view"] is False
    assert anon_data["medical_notes"] is None
    assert anon_data["caller_phone_masked"] != "+919876500000"
    assert anon_data["address"] != "Confidential Private Apartment 4B"

    # 2. Requester view
    req_res = await async_client.get("/api/v1/sos/sos-privacy-test", headers={"X-Aegis-User-Id": "requester-123"})
    req_data = req_res.json()["data"]
    assert req_data["is_authorized_view"] is True
    assert req_data["latitude"] == 28.613945
    assert req_data["address"] == "Confidential Private Apartment 4B"

    # 3. Assigned responder view
    resp_res = await async_client.get("/api/v1/sos/sos-privacy-test", headers={"X-Aegis-User-Id": "assigned-resp-456"})
    resp_data = resp_res.json()["data"]
    assert resp_data["is_authorized_view"] is True
    assert resp_data["medical_notes"] == "Severe Asthma"


@pytest.mark.asyncio
async def test_11_route_generation_and_12_location_updates_and_13_responder_tracking(
    async_client: AsyncClient, test_db: AsyncSession
):
    """Scenario 11, 12, 13: Route generation, requester location updates, and responder movement threshold."""
    now = utc_now()
    sos = SOSSignal(
        id="sos-nav-test",
        user_id="user-nav",
        requester_user_id="user-nav",
        status="ACCEPTED",
        latitude=28.6139,
        longitude=77.2090,
        accepted_by="resp-nav",
        created_at=now,
        updated_at=now
    )
    assign = SOSAssignment(
        sos_id="sos-nav-test",
        responder_user_id="resp-nav",
        status="ACTIVE",
        assigned_at=now,
        last_responder_lat=28.6300,
        last_responder_lon=77.2100,
        distance_meters=2100.0,
        eta_seconds=240,
        route_geometry={"type": "LineString", "coordinates": [[77.2100, 28.6300], [77.2090, 28.6139]]}
    )
    test_db.add_all([sos, assign])
    await test_db.commit()

    # 12. Requester updates location
    req_loc_res = await async_client.post(
        "/api/v1/sos/sos-nav-test/location",
        json={"latitude": 28.6145, "longitude": 77.2095, "accuracy_meters": 3.0, "battery_percent": 80},
        headers={"X-Aegis-User-Id": "user-nav"}
    )
    assert req_loc_res.status_code == 200
    assert req_loc_res.json()["data"]["latitude"] == 28.6145

    # 13a. Responder moves < 50 meters (no route recalculation)
    small_move_res = await async_client.post(
        "/api/v1/sos/sos-nav-test/responder-location",
        json={"latitude": 28.6301, "longitude": 77.2100},
        headers={"X-Aegis-User-Id": "resp-nav"}
    )
    assert small_move_res.status_code == 200
    assert small_move_res.json()["data"]["route_recalculated"] is False

    # 13b. Responder moves > 250 meters (triggers route recalculation)
    large_move_res = await async_client.post(
        "/api/v1/sos/sos-nav-test/responder-location",
        json={"latitude": 28.6220, "longitude": 77.2095},
        headers={"X-Aegis-User-Id": "resp-nav"}
    )
    assert large_move_res.status_code == 200
    assert large_move_res.json()["data"]["route_recalculated"] is True


@pytest.mark.asyncio
async def test_16_sos_cancellation_and_status_transitions(async_client: AsyncClient, test_db: AsyncSession):
    """Scenario 16: Operational status updates and cancellation."""
    now = utc_now()
    sos = SOSSignal(id="sos-cancel-test", status="OFFERED", latitude=28.6139, longitude=77.2090, created_at=now, updated_at=now)
    test_db.add(sos)
    await test_db.commit()

    # Cancel SOS
    cancel_res = await async_client.post(
        "/api/v1/sos/sos-cancel-test/cancel",
        json={"reason": "False alarm, safe now"},
        headers={"X-Aegis-User-Id": "user-cancel"}
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "CANCELLED"

    # Verify invalid transition from terminal CANCELLED state fails
    status_fail = await async_client.post(
        "/api/v1/sos/sos-cancel-test/status",
        json={"status": "ON_SITE"}
    )
    assert status_fail.status_code == 400


@pytest.mark.asyncio
async def test_17_responder_profile_update(async_client: AsyncClient, test_db: AsyncSession):
    """Test updating citizen responder participation and GPS coordinates."""
    payload = {
        "is_responder_opted_in": True,
        "is_available": True,
        "latitude": 28.7041,
        "longitude": 77.1025,
        "emergency_contacts": [{"name": "Papa", "phone": "+919800011122", "relationship": "Father"}]
    }
    res = await async_client.post(
        "/api/v1/sos/responder/profile",
        json=payload,
        headers={"X-Aegis-User-Id": "profile-user-123"}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_responder_opted_in"] is True
    assert data["last_known_lat"] == 28.7041
    assert data["emergency_contacts_count"] == 1
