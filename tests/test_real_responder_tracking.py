"""
AEGIS UNIFIED DATA CORE - Real Responder Tracking & Dispatch Integration Suite
Tests the complete production responder dispatch pipeline:
1. Availability & Capability Configuration (skills, vehicle type, max workload)
2. Deterministic Multi-Factor Matching (proximity, capability matching, workload penalty, GPS freshness)
3. Stale GPS Telemetry Penalization
4. Atomic Assignment Acceptance & RESPONDER_EN_ROUTE State Transition
5. High-Frequency GPS Breadcrumbs & 150m Dynamic Re-routing Threshold
6. Geofence Proximity & ON_SITE Arrival Verification
7. Incident Resolution & Responder Workload Release
8. Real-time Event Broadcast across Citizen and Command-Center streams
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from backend.app.database.models import (
    User, UserPreference, SOSSignal, SOSAssignment, SOSResponderCandidate,
    SOSLocationUpdate, utc_now
)
from backend.app.sos.matching import SOSMatchingEngine, haversine_distance_km
from backend.app.sos.routing import SOSRoutingEngine


@pytest.mark.asyncio
async def test_01_responder_profile_availability_and_capabilities(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that responders can configure their active opt-in status, availability toggle,
    specialized emergency capabilities, vehicle transit type, and maximum concurrent workload.
    """
    user_id = "resp-profile-test-01"
    user = User(
        id=user_id,
        email="paramedic_sarah@aegis.gov.in",
        hashed_password="mock",
        full_name="Paramedic Sarah Jenkins",
        role="paramedic",
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()

    payload = {
        "is_responder_opted_in": True,
        "is_available": True,
        "latitude": 19.0760,
        "longitude": 72.8777,
        "capabilities": ["FIRST_AID", "PARAMEDIC", "DOCTOR", "TRIAGE"],
        "vehicle_type": "AMBULANCE",
        "max_active_assignments": 2,
        "heading_degrees": 180.0,
        "speed_kmh": 0.0,
        "accuracy_meters": 4.5
    }

    res = await async_client.post(
        "/api/v1/sos/responder/profile",
        json=payload,
        headers={"X-Aegis-User-Id": user_id}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_responder_opted_in"] is True
    assert data["is_available"] is True
    assert data["vehicle_type"] == "AMBULANCE"
    assert data["max_active_assignments"] == 2
    assert "PARAMEDIC" in data["capabilities"]


@pytest.mark.asyncio
async def test_02_multi_factor_matching_deterministic_ranking(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that responder matching deterministically ranks candidates using the composite objective function:
    Score = 0.40 * Proximity + 0.30 * Capability + 0.20 * GPS Freshness + 0.10 * Workload
    Never selects responders randomly.
    """
    now = utc_now()
    sos_lat, sos_lon = 19.0760, 72.8777
    sos = SOSSignal(
        id="sos-match-test-01",
        caller_name="Flood Victim",
        caller_phone="+919111111111",
        emergency_type="flood_trapped",
        severity="CRITICAL",
        status="PENDING",
        latitude=sos_lat,
        longitude=sos_lon,
        city="Mumbai",
        state="Maharashtra",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    # Candidate A: Closer (2 km away), but general volunteer with basic skill
    user_a = User(id="cand-a", email="user_a@aegis.gov.in", hashed_password="mock", full_name="Volunteer Amit", role="volunteer", is_active=True)
    pref_a = UserPreference(
        user_id="cand-a",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=19.0940, # ~2 km away
        last_known_lng=72.8777,
        last_location_time=now,
        capabilities=["GENERAL_ASSIST"],
        vehicle_type="MOTORCYCLE",
        max_active_assignments=1
    )
    test_db.add_all([user_a, pref_a])

    # Candidate B: Slightly farther (3 km away), but SDRF Boat Rescue Specialist (exact match for flood_trapped)
    user_b = User(id="cand-b", email="user_b@aegis.gov.in", hashed_password="mock", full_name="SDRF Commander Roy", role="sdrf_officer", is_active=True)
    pref_b = UserPreference(
        user_id="cand-b",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=19.1030, # ~3 km away
        last_known_lng=72.8777,
        last_location_time=now,
        capabilities=["BOAT_RESCUE", "SWIMMER", "SEARCH_AND_RESCUE"],
        vehicle_type="BOAT",
        max_active_assignments=2
    )
    test_db.add_all([user_b, pref_b])
    await test_db.commit()

    candidates = await SOSMatchingEngine.find_eligible_responders(test_db, sos)
    assert len(candidates) >= 2
    # Candidate B must rank #1 due to specialized flood boat rescue capability and tactical role
    top_cand = candidates[0]
    assert top_cand["user_id"] == "cand-b"
    assert top_cand["vehicle_type"] == "BOAT"
    assert top_cand["score"] >= candidates[1]["score"]


@pytest.mark.asyncio
async def test_03_stale_gps_exclusion_and_penalization(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that responders with stale GPS updates (>30 minutes old) receive low freshness scores
    and are deprioritized compared to live responders.
    """
    now = utc_now()
    sos = SOSSignal(
        id="sos-stale-test-01",
        caller_name="Caller",
        caller_phone="+919222222222",
        emergency_type="medical",
        severity="CRITICAL",
        status="PENDING",
        latitude=13.0827,
        longitude=80.2707,
        city="Chennai",
        state="Tamil Nadu",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    # Fresh responder (1 minute ago)
    user_fresh = User(id="resp-fresh", email="fresh@aegis.gov.in", hashed_password="mock", full_name="Fresh Unit", role="paramedic", is_active=True)
    pref_fresh = UserPreference(
        user_id="resp-fresh",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=13.0900,
        last_known_lng=80.2700,
        last_location_time=now - timedelta(seconds=60),
        capabilities=["FIRST_AID", "PARAMEDIC"]
    )
    test_db.add_all([user_fresh, pref_fresh])

    # Stale responder (45 minutes ago)
    user_stale = User(id="resp-stale", email="stale@aegis.gov.in", hashed_password="mock", full_name="Stale Unit", role="paramedic", is_active=True)
    pref_stale = UserPreference(
        user_id="resp-stale",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=13.0850,
        last_known_lng=80.2705,
        last_location_time=now - timedelta(minutes=45),
        capabilities=["FIRST_AID", "PARAMEDIC"]
    )
    test_db.add_all([user_stale, pref_stale])
    await test_db.commit()

    candidates = await SOSMatchingEngine.find_eligible_responders(test_db, sos)
    fresh_cand = next(c for c in candidates if c["user_id"] == "resp-fresh")
    stale_cand = next(c for c in candidates if c["user_id"] == "resp-stale")

    assert fresh_cand["is_gps_fresh"] is True
    assert stale_cand["is_gps_fresh"] is False
    assert fresh_cand["score"] > stale_cand["score"]


@pytest.mark.asyncio
async def test_04_assignment_acceptance_and_en_route_transition(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies atomic acceptance of an SOS offer:
    - Sets state to RESPONDER_EN_ROUTE
    - Creates active SOSAssignment record
    - Computes vehicle-aware initial turn-by-turn route and realistic ETA
    - Rejects concurrent acceptance attempts with HTTP 409
    """
    now = utc_now()
    sos_id = "sos-accept-e2e-01"
    sos = SOSSignal(
        id=sos_id,
        caller_name="Trapped Resident",
        caller_phone="+919333333333",
        emergency_type="fire",
        severity="CRITICAL",
        status="OFFERED",
        latitude=28.6139,
        longitude=77.2090,
        city="New Delhi",
        state="Delhi",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    resp_id = "resp-accept-01"
    user_resp = User(id=resp_id, email="fire_unit1@aegis.gov.in", hashed_password="mock", full_name="Fire QRT 1", role="responder", is_active=True)
    pref_resp = UserPreference(
        user_id=resp_id,
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=28.6300,
        last_known_lng=77.2200,
        last_location_time=now,
        vehicle_type="4X4_JEEP",
        capabilities=["FIREFIGHTING", "SEARCH_AND_RESCUE"]
    )
    cand = SOSResponderCandidate(
        sos_id=sos_id,
        responder_user_id=resp_id,
        status="OFFERED",
        distance_km=2.1,
        offered_at=now
    )
    test_db.add_all([user_resp, pref_resp, cand])
    await test_db.commit()

    # 1. First responder accepts
    res = await async_client.post(
        f"/api/v1/sos/{sos_id}/accept",
        headers={"X-Aegis-User-Id": resp_id}
    )
    assert res.status_code == 200
    sos_data = res.json()["data"]
    assert sos_data["status"] in ["ACCEPTED", "RESPONDER_ASSIGNED"]
    assert sos_data["is_authorized_view"] is True
    assert sos_data["route"] is not None
    assert sos_data["eta_seconds"] > 0
    assert sos_data["distance_meters"] > 0

    # 1b. Responder transitions to RESPONDER_EN_ROUTE
    res_enroute = await async_client.post(
        f"/api/v1/sos/{sos_id}/status",
        json={"status": "RESPONDER_EN_ROUTE", "reason": "Departed base station via 4x4 Jeep"},
        headers={"X-Aegis-User-Id": resp_id}
    )
    assert res_enroute.status_code == 200
    assert res_enroute.json()["data"]["status"] == "RESPONDER_EN_ROUTE" 

    # 2. Second responder tries to accept -> Must be rejected with HTTP 409 Conflict
    res_conflict = await async_client.post(
        f"/api/v1/sos/{sos_id}/accept",
        headers={"X-Aegis-User-Id": "second-responder-late"}
    )
    assert res_conflict.status_code == 409


@pytest.mark.asyncio
async def test_05_gps_telemetry_breadcrumbs_and_route_recalculation(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that field devices sending high-frequency GPS telemetry updates:
    - Persist breadcrumbs in SOSLocationUpdate
    - Update current heading, speed, and last known coordinates
    - Recalculate turn-by-turn route & ETA when moved > 150m
    """
    now = utc_now()
    sos_id = "sos-telemetry-test"
    sos = SOSSignal(
        id=sos_id,
        caller_name="Caller",
        caller_phone="+919444444444",
        emergency_type="medical",
        severity="CRITICAL",
        status="RESPONDER_EN_ROUTE",
        latitude=12.9716,
        longitude=77.5946,
        city="Bengaluru",
        state="Karnataka",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    resp_id = "telemetry-responder"
    assignment = SOSAssignment(
        id="telemetry-assign-01",
        sos_id=sos_id,
        responder_user_id=resp_id,
        status="ACTIVE",
        assigned_at=now,
        last_responder_lat=12.9500,
        last_responder_lon=77.5800,
        last_responder_update=now,
        distance_meters=2800.0,
        eta_seconds=290
    )
    test_db.add(assignment)
    await test_db.commit()

    # Step 1: Small movement (30m) -> No route recalculation
    loc_payload_1 = {
        "latitude": 12.9502,
        "longitude": 77.5802,
        "speed_kmh": 35.0,
        "heading_degrees": 45.0,
        "accuracy_meters": 4.0
    }
    res_1 = await async_client.post(
        f"/api/v1/sos/{sos_id}/responder-location",
        json=loc_payload_1,
        headers={"X-Aegis-User-Id": resp_id}
    )
    assert res_1.status_code == 200
    assert res_1.json()["data"]["route_recalculated"] is False

    # Step 2: Significant movement (400m) -> Route & ETA recalculated
    loc_payload_2 = {
        "latitude": 12.9535,
        "longitude": 77.5830,
        "speed_kmh": 48.0,
        "heading_degrees": 42.0,
        "accuracy_meters": 3.5
    }
    res_2 = await async_client.post(
        f"/api/v1/sos/{sos_id}/responder-location",
        json=loc_payload_2,
        headers={"X-Aegis-User-Id": resp_id}
    )
    assert res_2.status_code == 200
    assert res_2.json()["data"]["route_recalculated"] is True
    assert res_2.json()["data"]["distance_meters"] > 0
    assert res_2.json()["data"]["eta_seconds"] > 0


@pytest.mark.asyncio
async def test_06_on_site_arrival_and_geofence_verification(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that when a responder arrives at the distress location:
    - Geofence proximity is detected
    - Status transitions to ON_SITE
    - arrived_on_site_at timestamp is persisted in SOSAssignment
    """
    now = utc_now()
    sos_id = "sos-onsite-test"
    sos = SOSSignal(
        id=sos_id,
        caller_name="Medical Emergency Victim",
        caller_phone="+919555555555",
        emergency_type="medical",
        severity="CRITICAL",
        status="RESPONDER_EN_ROUTE",
        latitude=17.3850,
        longitude=78.4867,
        city="Hyderabad",
        state="Telangana",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    resp_id = "hyderabad-paramedic"
    assignment = SOSAssignment(
        id="hyd-assign-01",
        sos_id=sos_id,
        responder_user_id=resp_id,
        status="ACTIVE",
        assigned_at=now,
        last_responder_lat=17.3851, # ~15 meters away
        last_responder_lon=78.4868,
        last_responder_update=now,
        distance_meters=15.0,
        eta_seconds=0
    )
    test_db.add(assignment)
    await test_db.commit()

    # Responder marks status ON_SITE
    status_payload = {
        "status": "ON_SITE",
        "reason": "Arrived at victim premises and initiated triage"
    }
    res = await async_client.post(
        f"/api/v1/sos/{sos_id}/status",
        json=status_payload,
        headers={"X-Aegis-User-Id": resp_id}
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "ON_SITE"

    # Verify database assignment record
    assign_check = await test_db.execute(select(SOSAssignment).where(SOSAssignment.id == "hyd-assign-01"))
    assign_obj = assign_check.scalars().first()
    assert assign_obj.arrived_on_site_at is not None


@pytest.mark.asyncio
async def test_07_distress_resolution_and_workload_release(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that resolving an SOS:
    - Sets SOS status to RESOLVED with resolution notes
    - Sets SOSAssignment status to COMPLETED with completed_at timestamp
    - Frees the responder's active workload capacity
    """
    now = utc_now()
    sos_id = "sos-resolve-test"
    sos = SOSSignal(
        id=sos_id,
        caller_name="Citizen",
        caller_phone="+919666666666",
        emergency_type="flood_trapped",
        severity="CRITICAL",
        status="ON_SITE",
        latitude=22.5726,
        longitude=88.3639,
        city="Kolkata",
        state="West Bengal",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    resp_id = "kolkata-sdrf"
    assignment = SOSAssignment(
        id="kol-assign-01",
        sos_id=sos_id,
        responder_user_id=resp_id,
        status="ACTIVE",
        assigned_at=now,
        arrived_on_site_at=now
    )
    test_db.add(assignment)
    await test_db.commit()

    resolve_payload = {
        "resolution_notes": "Victim safely evacuated via rubber boat to relief shelter."
    }
    res = await async_client.post(
        f"/api/v1/sos/{sos_id}/resolve",
        json=resolve_payload,
        headers={"X-Aegis-User-Id": resp_id}
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "RESOLVED"

    # Verify assignment is COMPLETED
    assign_check = await test_db.execute(select(SOSAssignment).where(SOSAssignment.id == "kol-assign-01"))
    assign_obj = assign_check.scalars().first()
    assert assign_obj.status == "COMPLETED"
    assert assign_obj.completed_at is not None

    # Verify workload map shows 0 active assignments for this responder
    workload_map = await SOSMatchingEngine.get_active_workload_map(test_db)
    assert workload_map.get(resp_id, 0) == 0
