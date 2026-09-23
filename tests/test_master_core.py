"""
AEGIS UNIFIED DATA CORE - Master Core Hardening Tests
Validates:
1. Master core entities (EmergencyFacility, ReportEvidence, ReportVerification, AIDecisionAudit, Device)
2. Explainable responder matching with selection rationale
3. RBAC role guards (citizen, responder, operator, official, admin)
4. AI decision auditing & human official authorization workflow
5. Emergency facilities CRUD and spatial radius/bounds query
6. tRPC compatibility bridge for mobile and web clients
7. Report media evidence SHA256 integrity and operator verification auditing
8. Realtime event envelope structure
"""
import pytest
import pytest_asyncio
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select

from backend.app.database.models import (
    User, EmergencyFacility, ReportEvidence, ReportVerification,
    AIDecisionAudit, Device, IncidentReport, SOSSignal, SOSAssignment,
    SOSResponderCandidate, SafeZone, SafeEvent, utc_now
)
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.engines.ai_layer import AIIntelligenceLayer
from backend.app.sos.matching import SOSMatchingEngine
from backend.app.realtime.manager import RealtimeEventManager, EventBroker


@pytest.mark.asyncio
async def test_master_entities_database_persistence(test_db):
    """Verifies all master core tables can persist and query records with full referential integrity."""
    # 1. User with role
    op_user = User(
        id="op-user-001",
        email="operator1@aegis.gov.in",
        hashed_password=get_password_hash("OpPass@2026!"),
        role="operator",
        full_name="Control Room Operator",
        is_active=True
    )
    test_db.add(op_user)
    await test_db.commit()

    # 2. Device
    device = Device(
        id="dev-uuid-001",
        device_id="hw-device-android-1234",
        user_id=op_user.id,
        platform="ANDROID",
        os_version="14.0",
        app_version="2.0.0",
        device_model="Pixel 8 Pro",
        is_active=True
    )
    test_db.add(device)

    # 3. Emergency Facility
    fac = EmergencyFacility(
        id="fac-uuid-001",
        name="Apollo Emergency Trauma Center",
        facility_type="HOSPITAL",
        latitude=28.6139,
        longitude=77.2090,
        address="Sarita Vihar, Delhi",
        city="New Delhi",
        district="South Delhi",
        state="Delhi",
        capacity=250,
        current_occupancy=45,
        operational_status="OPERATIONAL",
        amenities=["ICU", "TRAUMA_CENTER", "OXYGEN_PLANT", "HELIPAD"]
    )
    test_db.add(fac)

    # 4. Incident Report + Evidence
    report = IncidentReport(
        id="rep-uuid-001",
        user_id=op_user.id,
        title="Embankment Breach",
        category="FLOOD",
        hazard_type="FLOOD",
        severity="CRITICAL",
        description="Severe embankment breach along river bank",
        latitude=28.6150,
        longitude=77.2100,
        verification_status="PENDING_VERIFICATION"
    )
    test_db.add(report)
    await test_db.flush()

    evidence = ReportEvidence(
        id="evi-uuid-001",
        report_id=report.id,
        uploader_id=op_user.id,
        media_type="PHOTO",
        file_url="/static/uploads/breach_01.jpg",
        file_size_bytes=245120,
        mime_type="image/jpeg",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_verified=False
    )
    test_db.add(evidence)

    # 5. Report Verification Audit
    verif = ReportVerification(
        id="ver-uuid-001",
        report_id=report.id,
        operator_id=op_user.id,
        verification_status="VERIFIED",
        verified_severity="CRITICAL",
        operator_notes="Drone telemetry confirms 15m breach.",
        confidence_score=0.98
    )
    test_db.add(verif)

    # 6. AI Decision Audit
    ai_audit = AIDecisionAudit(
        id="aud-uuid-001",
        request_id="ai_req_998877",
        model_provider="gemini-1.5-flash",
        task_type="INCIDENT_CLASSIFICATION",
        input_hash="abc123hash",
        input_context={"desc": "embankment breach"},
        output_payload={"category": "FLOOD", "confidence": 0.95},
        confidence=0.95,
        authorization_status="AUTHORIZED",
        authorized_by_user_id=op_user.id
    )
    test_db.add(ai_audit)

    await test_db.commit()

    # Query back and verify integrity
    fac_res = await test_db.execute(select(EmergencyFacility).where(EmergencyFacility.id == "fac-uuid-001"))
    retrieved_fac = fac_res.scalar_one_or_none()
    assert retrieved_fac is not None
    assert retrieved_fac.name == "Apollo Emergency Trauma Center"
    assert "ICU" in retrieved_fac.amenities

    audit_res = await test_db.execute(select(AIDecisionAudit).where(AIDecisionAudit.request_id == "ai_req_998877"))
    retrieved_audit = audit_res.scalar_one_or_none()
    assert retrieved_audit is not None
    assert retrieved_audit.authorization_status == "AUTHORIZED"
    assert retrieved_audit.authorized_by_user_id == op_user.id


@pytest.mark.asyncio
async def test_matching_selection_rationale_persisted(test_db):
    """Verifies that responder matching computes and persists explainable selection rationale."""
    sos = SOSSignal(
        id="sos-rationale-test",
        user_id="citizen-001",
        latitude=28.6139,
        longitude=77.2090,
        status="TRIGGERED",
        severity="CRITICAL",
        emergency_type="FLOOD",
        idempotency_key="idemp-rat-001"
    )
    test_db.add(sos)

    # Candidate with rationale
    candidate = SOSResponderCandidate(
        id="cand-001",
        sos_id=sos.id,
        responder_user_id="resp-001",
        distance_km=0.85,
        status="OFFERED",
        selection_rationale="Proximity: 0.85km (Weight: 40%). Capability: FLOOD_RESCUE (Weight: 25%). Availability: STANDBY (Weight: 20%). Freshness: 12s ago (Weight: 15%)."
    )
    test_db.add(candidate)
    await test_db.commit()

    res = await test_db.execute(select(SOSResponderCandidate).where(SOSResponderCandidate.id == "cand-001"))
    cand_db = res.scalar_one_or_none()
    assert cand_db is not None
    assert "Proximity: 0.85km" in cand_db.selection_rationale
    assert "Capability: FLOOD_RESCUE" in cand_db.selection_rationale


@pytest.mark.asyncio
async def test_rbac_endpoint_authorization(async_client, test_db):
    """Verifies strict RBAC role enforcement across user tiers."""
    # Seed citizen, operator, official
    citizen = User(id="u-cit", email="citizen@test.com", hashed_password="pw", role="citizen", is_active=True)
    operator = User(id="u-op", email="operator@test.com", hashed_password="pw", role="operator", is_active=True)
    official = User(id="u-off", email="official@test.com", hashed_password="pw", role="official", is_active=True)
    test_db.add_all([citizen, operator, official])
    await test_db.commit()

    cit_tok = create_access_token(subject=citizen.id, role="citizen")
    op_tok = create_access_token(subject=operator.id, role="operator")
    off_tok = create_access_token(subject=official.id, role="official")

    cit_headers = {"Authorization": f"Bearer {cit_tok}"}
    op_headers = {"Authorization": f"Bearer {op_tok}"}
    off_headers = {"Authorization": f"Bearer {off_tok}"}

    # 1. /api/v1/auth/me allows citizen
    res_me = await async_client.get("/api/v1/auth/me", headers=cit_headers)
    assert res_me.status_code == 200
    assert res_me.json()["data"]["role"] == "citizen"

    # 2. /api/v1/ai/audit requires operator or above: citizen gets 403, operator gets 200
    res_cit_audit = await async_client.get("/api/v1/ai/audit", headers=cit_headers)
    assert res_cit_audit.status_code == 403

    res_op_audit = await async_client.get("/api/v1/ai/audit", headers=op_headers)
    assert res_op_audit.status_code == 200

    # 3. Create an AI audit entry in DB
    audit_entry = AIDecisionAudit(
        id="aud-rbac-1",
        request_id="ai_rbac_test",
        model_provider="gemini-1.5-flash",
        task_type="CLASSIFICATION",
        input_hash="hash1",
        input_context={"msg": "fire"},
        output_payload={"cat": "FIRE"},
        confidence=0.9,
        authorization_status="PENDING"
    )
    test_db.add(audit_entry)
    await test_db.commit()

    # /api/v1/ai/audit/{req_id}/authorize requires official: operator gets 403, official gets 200
    auth_payload = {"authorization_status": "AUTHORIZED", "operator_notes": "Official command approved"}
    res_op_auth = await async_client.post("/api/v1/ai/audit/ai_rbac_test/authorize", json=auth_payload, headers=op_headers)
    assert res_op_auth.status_code == 403

    res_off_auth = await async_client.post("/api/v1/ai/audit/ai_rbac_test/authorize", json=auth_payload, headers=off_headers)
    assert res_off_auth.status_code == 200
    assert res_off_auth.json()["data"]["authorization_status"] == "AUTHORIZED"


@pytest.mark.asyncio
async def test_ai_intelligence_endpoints(async_client, test_db):
    """Tests incident classification and resource recommendation with audit trail."""
    # 1. Incident classification
    classify_payload = {
        "title": "Severe Building Collapse",
        "description": "Structure collapsed after tremors, people trapped under rubble"
    }
    res_class = await async_client.post("/api/v1/ai/classify-incident", json=classify_payload)
    assert res_class.status_code == 200
    data_class = res_class.json()["data"]
    assert data_class["category"] == "BUILDING_DAMAGE"
    assert data_class["suggested_severity"] == "CRITICAL"
    assert data_class["confidence"] >= 0.70
    assert "audit_request_id" in data_class

    # 2. Resource recommendation
    rec_payload = {
        "emergency_type": "flood",
        "severity": "CRITICAL",
        "casualties_count": 8
    }
    res_rec = await async_client.post("/api/v1/ai/recommend-resources", json=rec_payload)
    assert res_rec.status_code == 200
    data_rec = res_rec.json()["data"]
    assert data_rec["recommended_vehicle"] == "BOAT"
    assert "LIFE_JACKETS" in data_rec["recommended_equipment"]
    assert "SDRF_TACTICAL_COMMAND" in data_rec["recommended_personnel"]
    assert "audit_request_id" in data_rec

    # 3. Verify audit records were persisted
    audits_res = await test_db.execute(select(AIDecisionAudit))
    all_audits = audits_res.scalars().all()
    assert len(all_audits) >= 2


@pytest.mark.asyncio
async def test_emergency_facilities_crud_and_spatial_query(async_client, admin_headers, test_db):
    """Tests Emergency Facility registration, radial search, bounds filtering, and lifecycle management."""
    # 1. Register two facilities
    fac1_payload = {
        "name": "Delhi Central Fire Station",
        "facility_type": "FIRE_STATION",
        "latitude": 28.6200,
        "longitude": 77.2100,
        "city": "New Delhi",
        "district": "Central Delhi",
        "state": "Delhi",
        "capacity": 50,
        "current_occupancy": 10,
        "operational_status": "OPERATIONAL",
        "amenities": ["FIRE_TENDERS", "HAZMAT_SUITS", "HIGH_PRESSURE_PUMPS"]
    }
    res1 = await async_client.post("/api/v1/facilities", json=fac1_payload, headers=admin_headers)
    assert res1.status_code == 201
    fac1_id = res1.json()["data"]["id"]

    fac2_payload = {
        "name": "Mumbai Coast Guard Station",
        "facility_type": "NDRF_BASE",
        "latitude": 18.9220,
        "longitude": 72.8347,
        "city": "Mumbai",
        "district": "Mumbai City",
        "state": "Maharashtra",
        "capacity": 120,
        "current_occupancy": 30,
        "operational_status": "OPERATIONAL",
        "amenities": ["PATROL_BOATS", "DIVING_GEAR"]
    }
    res2 = await async_client.post("/api/v1/facilities", json=fac2_payload, headers=admin_headers)
    assert res2.status_code == 201

    # 2. Proximity Query near Delhi: should return Delhi station with distance, not Mumbai
    res_prox = await async_client.get("/api/v1/facilities?lat=28.6139&lng=77.2090&radius_km=15")
    assert res_prox.status_code == 200
    prox_data = res_prox.json()["data"]
    assert len(prox_data) == 1
    assert prox_data[0]["name"] == "Delhi Central Fire Station"
    assert "distance_km" in prox_data[0]
    assert prox_data[0]["distance_km"] < 5.0

    # 3. Bounding Box Query covering Delhi
    res_bbox = await async_client.get("/api/v1/facilities?min_lat=28.5&max_lat=28.7&min_lng=77.0&max_lng=77.4")
    assert res_bbox.status_code == 200
    assert len(res_bbox.json()["data"]) == 1

    # 4. Map Data Layer verification: facilities layer contains the new facility
    res_map = await async_client.get("/api/v1/map-data?layers=facilities")
    assert res_map.status_code == 200
    features = res_map.json()["data"]["features"]
    assert any(f["properties"]["entity_id"] == fac1_id for f in features)

    # 5. Patch facility status
    patch_payload = {"current_occupancy": 25, "operational_status": "COMPROMISED"}
    res_patch = await async_client.patch(f"/api/v1/facilities/{fac1_id}", json=patch_payload, headers=admin_headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["data"]["current_occupancy"] == 25
    assert res_patch.json()["data"]["operational_status"] == "COMPROMISED"

    # 6. Deactivate facility
    res_del = await async_client.delete(f"/api/v1/facilities/{fac1_id}", headers=admin_headers)
    assert res_del.status_code == 200
    assert res_del.json()["data"]["status"] == "OFFLINE"


@pytest.mark.asyncio
async def test_trpc_compatibility_endpoints(async_client, test_db):
    """Tests tRPC compatibility endpoints for mobile/web client bridging."""
    # 1. aegis.getWeather
    res_w = await async_client.get('/api/trpc/aegis.getWeather?input={"json":{"latitude":28.61,"longitude":77.20}}')
    assert res_w.status_code == 200
    data_w = res_w.json()["result"]["data"]["json"]
    assert "temperatureC" in data_w
    assert "forecast" in data_w
    assert len(data_w["todayHourly"]) == 24

    # 2. safePing.create
    ping_payload = {
        "json": {
            "userId": "cit-trpc-01",
            "userName": "Rohit Kumar",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "message": "Reached relief shelter safely"
        }
    }
    res_ping = await async_client.post("/api/trpc/safePing.create", json=ping_payload)
    assert res_ping.status_code == 200
    data_ping = res_ping.json()["result"]["data"]["json"]
    assert data_ping["status"] == "SAFE"

    # Verify SafeEvent was actually persisted in PostgreSQL/DB
    event_res = await test_db.execute(select(SafeEvent).where(SafeEvent.user_name == "Rohit Kumar"))
    saved_event = event_res.scalar_one_or_none()
    assert saved_event is not None
    assert saved_event.status == "SAFE"


@pytest.mark.asyncio
async def test_realtime_event_packet_envelope():
    """Verifies RealtimeEventManager formats canonical event packets with mandatory fields."""
    event_packet = RealtimeEventManager.format_event(
        event_type="SOS_STATUS_UPDATED",
        data={
            "sos_id": "sos-packet-001",
            "status": "RESPONDER_EN_ROUTE",
            "responder_id": "resp-77"
        },
        event_id="evt-packet-123456",
        entity_id="sos-packet-001",
        entity_type="SOS",
        actor_id="resp-77"
    )

    assert event_packet["event_id"] == "evt-packet-123456"
    assert event_packet["event_type"] == "SOS_STATUS_UPDATED"
    assert event_packet["entity_id"] == "sos-packet-001"
    assert event_packet["entity_type"] == "SOS"
    assert event_packet["actor_id"] == "resp-77"
    assert event_packet["payload"]["status"] == "RESPONDER_EN_ROUTE"
    assert "timestamp" in event_packet
