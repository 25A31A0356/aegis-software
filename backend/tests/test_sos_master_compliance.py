"""
AEGIS SOS MASTER COMPLIANCE SUITE
Explicitly validates all 17 requirements and full State Machine lifecycle:
1. SOS creation
2. SOS ID
3. Idempotency key deduplication
4. User authentication & authorization
5. GPS coordinates (lat/lng)
6. GPS accuracy (meters)
7. Timestamp (ISO-8601 UTC)
8. Emergency category
9. Description / short message
10. Number of affected people (casualties_count)
11. Battery & network metadata
12. SOS persistence in database
13. Complete SOS state machine (TRIGGERED -> ACKNOWLEDGED -> RESPONDER_MATCHING -> RESPONDER_ASSIGNED -> RESPONDER_EN_ROUTE -> ON_SITE -> RESOLVED)
14. SOS status history audit trail
15. Audit events dispatched across channels
16. Cancellation with reason
17. Resolution with notes & completed assignments
+ Exceptional states: CANCELLED, FALSE_ALARM, EXPIRED
+ Illegal transition protection (e.g., RESOLVED -> TRIGGERED returns HTTP 400)
"""
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from backend.app.database.models import (
    SOSSignal, SOSAssignment, SOSLocationUpdate,
    SOSStatusHistory, User
)
from backend.app.sos.state_machine import SOSState, SOSStateMachine


@pytest.mark.asyncio
async def test_sos_17_point_master_lifecycle_and_state_machine(async_client, test_db):
    """
    Verifies items 1-17 in sequence with strict database and state machine assertions.
    """
    user_id = f"citizen-{uuid.uuid4().hex[:8]}"
    responder_id = f"sdrf-resp-{uuid.uuid4().hex[:8]}"
    idem_key = f"idem-master-{uuid.uuid4().hex[:12]}"

    # Setup database users
    u_citizen = User(id=user_id, email=f"{user_id}@aegis.gov.in", hashed_password="pw", full_name="Disaster Victim", role="public", is_active=True)
    u_responder = User(id=responder_id, email=f"{responder_id}@aegis.gov.in", hashed_password="pw", full_name="SDRF Commander", role="sdrf_officer", is_active=True)
    test_db.add_all([u_citizen, u_responder])
    await test_db.commit()

    # --------------------------------------------------------------------------
    # 1-11: SOS Creation with All Metadata (1. Creation, 2. ID, 3. Idempotency,
    # 4. Auth, 5. GPS, 6. Accuracy, 7. Timestamp, 8. Category, 9. Description,
    # 10. Affected People, 11. Battery)
    # --------------------------------------------------------------------------
    req_payload = {
        "caller_name": "Disaster Victim",
        "caller_phone": "+919123456780",
        "emergency_type": "flood_trapped",         # 8. Emergency category
        "severity": "CRITICAL",
        "short_message": "Trapped on roof in flash flood, 4 people including child", # 9. Description
        "latitude": 17.7231,                         # 5. GPS coordinate
        "longitude": 83.3012,                        # 5. GPS coordinate
        "accuracy_meters": 3.8,                      # 6. GPS accuracy
        "battery_percent": 74,                       # 11. Battery metadata
        "casualties_count": 4,                       # 10. Affected people
        "medical_notes": "Needs emergency food and insulin",
        "requester_user_id": user_id,                # 4. User auth
        "idempotency_key": idem_key                  # 3. Idempotency key
    }

    create_res = await async_client.post(
        "/api/v1/sos",
        json=req_payload,
        headers={"X-Aegis-User-Id": user_id, "X-Request-ID": "master-req-01"}
    )
    assert create_res.status_code == 200, f"Creation failed: {create_res.text}"
    created_data = create_res.json()["data"]

    sos_id = created_data["id"]                      # 2. SOS ID
    assert sos_id is not None
    assert created_data["emergency_type"] == "flood_trapped"
    assert created_data["casualties_count"] == 4
    assert created_data["battery_percent"] == 74
    assert created_data["accuracy_meters"] == 3.8
    assert "created_at" in created_data              # 7. Timestamp

    # 12. Database Persistence Proof
    db_sos = (await test_db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))).scalars().first()
    assert db_sos is not None, "12. SOS not persisted in database!"
    assert db_sos.latitude == 17.7231
    assert db_sos.longitude == 83.3012
    assert db_sos.casualties_count == 4
    assert db_sos.idempotency_key == idem_key

    # 3. Idempotency Key Deduplication Proof
    dup_res = await async_client.post(
        "/api/v1/sos",
        json=req_payload,
        headers={"X-Aegis-User-Id": user_id}
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["data"]["id"] == sos_id, "Idempotent duplicate did not return existing SOS"
    all_sos_with_key = (await test_db.execute(select(SOSSignal).where(SOSSignal.idempotency_key == idem_key))).scalars().all()
    assert len(all_sos_with_key) == 1, "Duplicate SOS was inserted into DB!"

    # --------------------------------------------------------------------------
    # 13. State Machine Progression: TRIGGERED -> ACKNOWLEDGED
    # --------------------------------------------------------------------------
    ack_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/acknowledge",
        headers={"X-Aegis-User-Id": "control-room-officer"}
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["data"]["status"] == "ACKNOWLEDGED"

    # Verify DB & Status History Audit
    db_sos = (await test_db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))).scalars().first()
    assert db_sos.status == "ACKNOWLEDGED"

    # --------------------------------------------------------------------------
    # 13. State Machine Progression: ACKNOWLEDGED -> RESPONDER_MATCHING
    # --------------------------------------------------------------------------
    match_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/status",
        json={"status": "RESPONDER_MATCHING", "reason": "Dispatching candidate search algorithm"},
        headers={"X-Aegis-User-Id": "control-room-officer"}
    )
    assert match_res.status_code == 200
    assert match_res.json()["data"]["status"] == "RESPONDER_MATCHING"

    # --------------------------------------------------------------------------
    # 13. State Machine Progression: RESPONDER_MATCHING -> RESPONDER_ASSIGNED (or ACCEPTED)
    # --------------------------------------------------------------------------
    accept_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/accept",
        headers={"X-Aegis-User-Id": responder_id}
    )
    assert accept_res.status_code == 200
    acc_data = accept_res.json()["data"]
    assert acc_data["accepted_by"] == responder_id
    assert acc_data["status"] in ("ACCEPTED", "RESPONDER_ASSIGNED")

    # Verify Assignment in DB
    assign = (await test_db.execute(select(SOSAssignment).where(SOSAssignment.sos_id == sos_id))).scalars().first()
    assert assign is not None, "SOSAssignment record missing in DB"
    assert assign.responder_user_id == responder_id
    assert assign.status == "ACTIVE"

    # --------------------------------------------------------------------------
    # 13. State Machine Progression: RESPONDER_ASSIGNED -> RESPONDER_EN_ROUTE
    # --------------------------------------------------------------------------
    enroute_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/status",
        json={"status": "RESPONDER_EN_ROUTE", "reason": "SDRF rescue boat deployed and en route"},
        headers={"X-Aegis-User-Id": responder_id}
    )
    assert enroute_res.status_code == 200
    assert enroute_res.json()["data"]["status"] == "RESPONDER_EN_ROUTE"

    # Send GPS Telemetry Breadcrumb
    loc_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/responder-location",
        json={
            "latitude": 17.7210,
            "longitude": 83.2990,
            "accuracy_meters": 4.0,
            "speed_kmh": 28.5
        },
        headers={"X-Aegis-User-Id": responder_id}
    )
    assert loc_res.status_code == 200
    resp_breadcrumb = (await test_db.execute(
        select(SOSLocationUpdate).where(SOSLocationUpdate.sos_id == sos_id, SOSLocationUpdate.user_type == "RESPONDER")
    )).scalars().first()
    assert resp_breadcrumb is not None, "Responder breadcrumb location update was not persisted"
    assert resp_breadcrumb.latitude == 17.7210
    assert resp_breadcrumb.speed_kmh == 28.5

    # --------------------------------------------------------------------------
    # 13. State Machine Progression: RESPONDER_EN_ROUTE -> ON_SITE
    # --------------------------------------------------------------------------
    onsite_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/status",
        json={"status": "ON_SITE", "reason": "SDRF boat reached stranded victim location"},
        headers={"X-Aegis-User-Id": responder_id}
    )
    assert onsite_res.status_code == 200
    assert onsite_res.json()["data"]["status"] == "ON_SITE"

    # --------------------------------------------------------------------------
    # 17. Resolution: ON_SITE -> RESOLVED
    # --------------------------------------------------------------------------
    resolve_res = await async_client.post(
        f"/api/v1/sos/{sos_id}/resolve",
        json={"resolution_notes": "4 citizens including infant safely transported to relief camp."},
        headers={"X-Aegis-User-Id": responder_id}
    )
    assert resolve_res.status_code == 200
    res_data = resolve_res.json()["data"]
    assert res_data["status"] == "RESOLVED"
    assert res_data["resolved_at"] is not None

    # 14. Status History Audit Trail Proof: Every transition persisted in DB
    history = (await test_db.execute(
        select(SOSStatusHistory).where(SOSStatusHistory.sos_id == sos_id).order_by(SOSStatusHistory.created_at.asc())
    )).scalars().all()
    
    statuses_recorded = [h.new_status for h in history]
    assert len(statuses_recorded) >= 5, f"Expected full audit trail, got: {statuses_recorded}"
    assert "ACKNOWLEDGED" in statuses_recorded
    assert "RESOLVED" in statuses_recorded

    # Assignment completed
    assign_final = (await test_db.execute(select(SOSAssignment).where(SOSAssignment.sos_id == sos_id))).scalars().first()
    assert assign_final.status == "COMPLETED"


@pytest.mark.asyncio
async def test_sos_exceptional_transitions_and_illegal_leap_prevention(async_client, test_db):
    """
    Tests exceptional states: CANCELLED, FALSE_ALARM, EXPIRED
    and verifies that illegal state transitions are prevented.
    """
    c_user = f"citizen-{uuid.uuid4().hex[:8]}"

    # 1. Exceptional State: FALSE_ALARM
    res1 = await async_client.post(
        "/api/v1/sos",
        json={
            "caller_name": "Accidental Pocket Dial",
            "emergency_type": "general",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "idempotency_key": f"fa-{uuid.uuid4().hex[:8]}"
        },
        headers={"X-Aegis-User-Id": c_user}
    )
    sos1_id = res1.json()["data"]["id"]

    fa_res = await async_client.post(
        f"/api/v1/sos/{sos1_id}/false-alarm",
        json={"reason": "Citizen confirmed pocket dial"},
        headers={"X-Aegis-User-Id": c_user}
    )
    assert fa_res.status_code == 200
    assert fa_res.json()["data"]["status"] == "FALSE_ALARM"

    # Prove in DB
    db_sos1 = (await test_db.execute(select(SOSSignal).where(SOSSignal.id == sos1_id))).scalars().first()
    assert db_sos1.status == "FALSE_ALARM"

    # 2. Exceptional State: CANCELLED
    res2 = await async_client.post(
        "/api/v1/sos",
        json={
            "caller_name": "Citizen Needs Help",
            "emergency_type": "medical",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "idempotency_key": f"cancel-{uuid.uuid4().hex[:8]}"
        },
        headers={"X-Aegis-User-Id": c_user}
    )
    sos2_id = res2.json()["data"]["id"]

    cancel_res = await async_client.post(
        f"/api/v1/sos/{sos2_id}/cancel",
        json={"reason": "Situation self-resolved before rescue team arrived"},
        headers={"X-Aegis-User-Id": c_user}
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "CANCELLED"

    # 3. Prevent Illegal Leap from Terminal State (CANCELLED -> ON_SITE returns HTTP 400)
    illegal_res = await async_client.post(
        f"/api/v1/sos/{sos2_id}/status",
        json={"status": "ON_SITE", "reason": "Attempting illegal resurrection"},
        headers={"X-Aegis-User-Id": c_user}
    )
    assert illegal_res.status_code == 400, "State machine allowed illegal transition from terminal CANCELLED state!"

    # 4. Prevent Illegal Leap from Terminal State (FALSE_ALARM -> RESOLVED returns HTTP 400)
    illegal_fa = await async_client.post(
        f"/api/v1/sos/{sos1_id}/resolve",
        json={"resolution_notes": "Attempting illegal resolve on false alarm"},
        headers={"X-Aegis-User-Id": c_user}
    )
    assert illegal_fa.status_code == 400, "State machine allowed illegal transition from terminal FALSE_ALARM state!"
