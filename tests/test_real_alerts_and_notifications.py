"""
AEGIS UNIFIED DATA CORE - Real Alerts and Push Notifications Test Suite
Verifies:
1. Alert Schema & Fields: id, type, severity, title, description, source, location, created_at, updated_at, expires_at, status
2. Strict 4-Tier Provenance Taxonomy: OFFICIAL ALERT, SYSTEM ALERT, COMMUNITY REPORT, AI GENERATED INFORMATION
3. Mandatory AI Authorization Guardrail: AI can never directly publish official alerts; operator promotion workflow
4. Push Notification Architecture & Device Token Registration
5. 4 Required Notification Types: SOS Assignment, SOS Status, Critical Alert, Report Verification
6. Delivery Acknowledgements (DISPATCHED -> DELIVERED) and Provider Rejection (REJECTED_BY_PROVIDER - never 'sent' on rejection)
"""
import pytest
import uuid
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.database.models import (
    AlertRecord, DeviceToken, NotificationDeliveryRecord,
    IncidentReport, SOSSignal, User, utc_now
)
from backend.app.notifications.service import PushNotificationService


# ==============================================================================
# 1. ALERT SCHEMA & REQUIRED PROPERTIES
# ==============================================================================

@pytest.mark.asyncio
async def test_alert_schema_and_required_fields(async_client: AsyncClient):
    """
    Alerts must have: id, type, severity, title, description, source, location,
    created_at, updated_at, expires_at, status.
    """
    payload = {
        "title": "Severe Cyclone Warning: Coast of Andhra Pradesh",
        "description": "Category 4 Cyclone approaching with winds up to 160 km/h. Evacuation in progress.",
        "instruction": "Move to designated cyclone shelters immediately.",
        "hazard_type": "CYCLONE",
        "severity": "critical",
        "status": "active",
        "state_name": "Andhra Pradesh",
        "district_name": "Visakhapatnam",
        "latitude": 17.6868,
        "longitude": 83.2185,
        "radius_km": 75.0,
        "source": "IMD",
        "valid_hours": 36,
        "provenance_type": "OFFICIAL_ALERT"
    }

    response = await async_client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    alert = res_json["data"]

    # Verify all required fields from user prompt
    assert alert["id"] is not None and alert["id"].startswith("alert-")
    assert alert["type"] == "CYCLONE"
    assert alert["hazard_type"] == "CYCLONE"
    assert alert["severity"] == "critical"
    assert alert["title"] == payload["title"]
    assert alert["description"] == payload["description"]
    assert alert["source"] is not None
    assert alert["source"]["agency"] == "IMD"
    assert alert["location"] is not None
    assert alert["location"]["state"] == "Andhra Pradesh"
    assert alert["location"]["district"] == "Visakhapatnam"
    assert alert["location"]["coordinates"] == [17.6868, 83.2185]
    assert alert["location"]["radiusKm"] == 75.0
    assert alert["created_at"] is not None and len(alert["created_at"]) > 0
    assert alert["updated_at"] is not None and len(alert["updated_at"]) > 0
    assert alert["expires_at"] is not None and len(alert["expires_at"]) > 0
    assert alert["status"] == "active"
    assert alert["provenance_type"] == "OFFICIAL_ALERT"
    assert alert["is_authorized_official"] is True


# ==============================================================================
# 2. STRICT 4-TIER PROVENANCE TAXONOMY
# ==============================================================================

@pytest.mark.asyncio
async def test_strict_4_tier_provenance_distinction(async_client: AsyncClient):
    """
    Clearly distinguish:
    - OFFICIAL ALERT
    - SYSTEM ALERT
    - COMMUNITY REPORT
    - AI GENERATED INFORMATION
    """
    # 1. Official Alert
    off_res = await async_client.post("/api/v1/alerts", json={
        "title": "Official Flood Advisory - Godavari Basin",
        "description": "CWC river gauges have surpassed warning level.",
        "hazard_type": "FLOOD",
        "severity": "warning",
        "latitude": 16.9891,
        "longitude": 81.7840,
        "provenance_type": "OFFICIAL_ALERT"
    })
    assert off_res.status_code == 200
    assert off_res.json()["data"]["provenance_type"] == "OFFICIAL_ALERT"

    # 2. System Alert (Automated Sensor Thresholds)
    sys_res = await async_client.post("/api/v1/alerts", json={
        "title": "Automated Seismic Sensor Spike",
        "description": "Seismic accelerometer array detected M5.2 ground acceleration.",
        "hazard_type": "EARTHQUAKE",
        "severity": "moderate",
        "latitude": 27.3389,
        "longitude": 88.6065,
        "source": "SYSTEM_SENSOR_ARRAY",
        "provenance_type": "SYSTEM_ALERT"
    })
    assert sys_res.status_code == 200
    assert sys_res.json()["data"]["provenance_type"] == "SYSTEM_ALERT"

    # 3. Community Report (Via Community Incident Endpoints)
    rep_res = await async_client.post("/api/v1/reports", json={
        "title": "Severe Waterlogging at Sub-way",
        "description": "Underpass submerged in 4 feet water, traffic halted.",
        "category": "WATERLOGGING",
        "severity": "HIGH",
        "latitude": 17.4065,
        "longitude": 78.4772
    })
    assert rep_res.status_code == 200
    rep_data = rep_res.json()["data"]
    assert rep_data["source"] == "COMMUNITY"
    assert rep_data["source_type"] == "COMMUNITY_REPORT"

    # 4. AI Generated Information
    ai_res = await async_client.post(
        "/api/v1/alerts",
        json={
            "title": "AI Predictive Flood Inundation Model",
            "description": "Predictive hydrological model indicates 78% probability of flash flood in 6 hours.",
            "hazard_type": "FLOOD",
            "severity": "warning",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "provenance_type": "AI_GENERATED_INFO",
            "is_ai_generated": True
        },
        headers={"X-Aegis-AI-Agent": "Aegis-LLM-Predictor"}
    )
    assert ai_res.status_code == 200
    ai_data = ai_res.json()["data"]
    assert ai_data["provenance_type"] == "AI_GENERATED_INFO"
    assert ai_data["status"] == "draft_pending_approval"
    assert ai_data["is_authorized_official"] is False


# ==============================================================================
# 3. MANDATORY AI AUTHORIZATION WORKFLOW GUARDRAIL
# ==============================================================================

@pytest.mark.asyncio
async def test_ai_alert_authorization_workflow(async_client: AsyncClient):
    """
    AI must never create an official alert without the required authorization workflow.
    - AI caller creates alert -> Saved as AI_GENERATED_INFO in DRAFT_PENDING_APPROVAL.
    - Operator reviews and promotes -> Becomes OFFICIAL_ALERT in ACTIVE status with audit record.
    """
    # 1. AI agent attempts to post an alert
    ai_response = await async_client.post(
        "/api/v1/alerts",
        json={
            "title": "AI Heatwave Assessment",
            "description": "Surface temperature telemetry suggests severe heat stress across district.",
            "hazard_type": "HEATWAVE",
            "severity": "warning",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "provenance_type": "OFFICIAL_ALERT", # AI trying to claim official alert
            "is_ai_generated": True
        },
        headers={"X-Aegis-AI-Agent": "Autonomous-Risk-Agent"}
    )
    assert ai_response.status_code == 200
    draft = ai_response.json()["data"]
    
    # GUARDRAIL ENFORCEMENT: AI cannot directly create an official alert
    assert draft["provenance_type"] == "AI_GENERATED_INFO"
    assert draft["status"] == "draft_pending_approval"
    assert draft["is_authorized_official"] is False
    alert_id = draft["id"]

    # 2. Public query does NOT show unapproved AI drafts by default
    public_list = await async_client.get("/api/v1/alerts")
    assert public_list.status_code == 200
    public_ids = [a["id"] for a in public_list.json()["data"]]
    assert alert_id not in public_ids

    # 3. Authorized Human Operator reviews and promotes the draft
    promote_res = await async_client.post(
        f"/api/v1/alerts/{alert_id}/authorize-official",
        json={
            "authorization_notes": "Reviewed and verified against ground telemetry by Lead Disaster Officer.",
            "signed_by": "officer_sharma_942"
        },
        headers={"X-Aegis-User-Id": "officer_sharma_942"}
    )
    assert promote_res.status_code == 200
    promoted = promote_res.json()["data"]

    # Verify promotion to OFFICIAL ALERT
    assert promoted["provenance_type"] == "OFFICIAL_ALERT"
    assert promoted["status"] == "active"
    assert promoted["is_authorized_official"] is True

    # 4. Now the alert appears in the official public alert feed
    refreshed_list = await async_client.get("/api/v1/alerts")
    assert alert_id in [a["id"] for a in refreshed_list.json()["data"]]


# ==============================================================================
# 4. MOBILE PUSH NOTIFICATION ARCHITECTURE & TOKEN REGISTRATION
# ==============================================================================

@pytest.mark.asyncio
async def test_device_push_token_registration(async_client: AsyncClient):
    """
    Test registration of mobile device push tokens (Expo, FCM, APNs).
    """
    dev_id = f"device_{uuid.uuid4().hex[:8]}"
    push_tok = f"ExponentPushToken[{uuid.uuid4().hex[:16]}]"

    reg_res = await async_client.post(
        "/api/v1/notifications/tokens/register",
        json={
            "device_id": dev_id,
            "push_token": push_tok,
            "platform": "ANDROID",
            "provider": "EXPO",
            "user_id": "citizen_user_01"
        }
    )
    assert reg_res.status_code == 200
    data = reg_res.json()["data"]
    assert data["device_id"] == dev_id
    assert data["push_token"] == push_tok
    assert data["platform"] == "ANDROID"
    assert data["is_active"] is True


# ==============================================================================
# 5. THE 4 REQUIRED NOTIFICATION TYPES
# ==============================================================================

@pytest.mark.asyncio
async def test_all_four_required_notification_types(async_client: AsyncClient, test_db: AsyncSession):
    """
    Implement:
    1. SOS assignment notification
    2. SOS status notification
    3. Critical alert notification
    4. Report verification notification
    """
    # Setup test responder & user device tokens
    resp_id = f"resp_{uuid.uuid4().hex[:6]}"
    cit_id = f"cit_{uuid.uuid4().hex[:6]}"
    await PushNotificationService.register_device_token(
        test_db, device_id=f"dev_{resp_id}", push_token=f"ExponentPushToken[test_{resp_id}]", platform="ANDROID", user_id=resp_id
    )
    await PushNotificationService.register_device_token(
        test_db, device_id=f"dev_{cit_id}", push_token=f"ExponentPushToken[test_{cit_id}]", platform="ANDROID", user_id=cit_id
    )

    # 1. SOS Assignment Notification
    sos_test = SOSSignal(
        id=f"sos-{uuid.uuid4().hex[:8]}",
        user_id=cit_id,
        requester_user_id=cit_id,
        caller_name="Ananya Rao",
        caller_phone="+919876543210",
        emergency_type="flood_trapped",
        severity="CRITICAL",
        latitude=17.6868,
        longitude=83.2185,
        district="Visakhapatnam",
        status="RESPONDER_MATCHING"
    )
    test_db.add(sos_test)
    await test_db.commit()

    assign_delivs = await PushNotificationService.dispatch_sos_assignment(
        db=test_db,
        sos=sos_test,
        candidate_responder_id=resp_id,
        distance_km=2.4
    )
    assert len(assign_delivs) >= 2
    types = [d.notification_type for d in assign_delivs]
    assert "SOS_ASSIGNMENT" in types
    statuses = [d.status for d in assign_delivs]
    assert "DISPATCHED" in statuses

    # 2. SOS Status Notification (e.g. RESPONDER_EN_ROUTE)
    sos_test.status = "RESPONDER_EN_ROUTE"
    await test_db.commit()
    status_delivs = await PushNotificationService.dispatch_sos_status(
        db=test_db,
        sos=sos_test,
        new_status="RESPONDER_EN_ROUTE",
        extra_data={"eta_minutes": 8}
    )
    assert len(status_delivs) >= 1
    assert status_delivs[0].notification_type == "SOS_STATUS"
    assert status_delivs[0].status == "DISPATCHED"
    assert "EN-ROUTE" in status_delivs[0].title

    # 3. Critical Alert Notification
    crit_alert = AlertRecord(
        id=f"alert-{uuid.uuid4().hex[:8]}",
        alert_code=f"IND-CYCLONE-{uuid.uuid4().hex[:4].upper()}",
        headline="Super Cyclone Landfall Imminent",
        description="High tidal surge and gale winds expected.",
        hazard_type="CYCLONE",
        severity="critical",
        status="active",
        latitude=17.6868,
        longitude=83.2185,
        source_agency="IMD",
        provenance_type="OFFICIAL_ALERT",
        is_authorized_official=True
    )
    test_db.add(crit_alert)
    await test_db.commit()

    crit_delivs = await PushNotificationService.dispatch_critical_alert(
        db=test_db,
        alert=crit_alert
    )
    assert len(crit_delivs) >= 1
    assert crit_delivs[0].notification_type == "CRITICAL_ALERT"
    assert "CRITICAL DISASTER ALERT" in crit_delivs[0].title

    # 4. Report Verification Notification
    report = IncidentReport(
        id=f"rep-{uuid.uuid4().hex[:8]}",
        user_id=cit_id,
        title="Landslide Blocking NH-16",
        description="Boulders fell across both lanes.",
        category="LANDSLIDE",
        hazard_type="LANDSLIDE",
        severity="HIGH",
        status="SUBMITTED",
        verification_status="UNVERIFIED",
        latitude=17.7500,
        longitude=83.3000
    )
    test_db.add(report)
    await test_db.commit()

    # Operator verifies report via API
    ver_res = await async_client.post(
        f"/api/v1/reports/{report.id}/verify",
        json={"operator_notes": "Ground inspection confirmed by SDRF Unit 3."}
    )
    assert ver_res.status_code == 200
    assert ver_res.json()["data"]["verification_status"] == "VERIFIED"

    # Verify report verification notification was dispatched
    deliveries_res = await async_client.get(f"/api/v1/notifications?user_id={cit_id}")
    assert deliveries_res.status_code == 200
    notifs = deliveries_res.json()["data"]
    ver_notif = next((n for n in notifs if n["notification_type"] == "REPORT_VERIFICATION"), None)
    assert ver_notif is not None
    assert ver_notif["status"] == "DISPATCHED"
    assert "REPORT VERIFIED" in ver_notif["title"]


# ==============================================================================
# 6. DELIVERY ACKNOWLEDGEMENT AND PROVIDER FAILURE HANDLING
# ==============================================================================

@pytest.mark.asyncio
async def test_delivery_acknowledgement_flow(async_client: AsyncClient):
    """
    Test client delivery acknowledgement:
    PENDING / DISPATCHED -> Client sends ACK -> DELIVERED.
    """
    # 1. Dispatch valid test push
    disp_res = await async_client.post(
        "/api/v1/notifications/test-dispatch",
        json={
            "device_token": "ExponentPushToken[valid_test_token_123]",
            "notification_type": "CRITICAL_ALERT",
            "title": "Tsunami Drill Advisory",
            "body": "Mock drill in coastal sectors."
        }
    )
    assert disp_res.status_code == 200
    deliv = disp_res.json()["data"]
    assert deliv["status"] == "DISPATCHED"
    notif_id = deliv["id"]

    # 2. Client sends Delivery ACK (with matching device token for authorization)
    ack_res = await async_client.post(
        f"/api/v1/notifications/{notif_id}/ack",
        json={
            "device_id": "test_recipient",
            "device_token": "ExponentPushToken[valid_test_token_123]",
            "client_timestamp": utc_now().isoformat(),
            "metadata": {"network": "5G", "battery": 88}
        }
    )
    assert ack_res.status_code == 200
    acked = ack_res.json()["data"]
    assert acked["status"] == "DELIVERED"
    assert acked["delivered_at"] is not None
    assert acked["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_provider_rejection_never_shows_sent(async_client: AsyncClient):
    """
    STRICT TRANSPARENCY CONSTRAINT:
    Do not display 'sent' when the notification provider rejected the request.
    If the provider returns an error (e.g. DeviceNotRegistered / InvalidRegistration),
    status MUST be REJECTED_BY_PROVIDER and NEVER 'SENT' or 'DELIVERED'.
    """
    # 1. Test dispatch with rejected/revoked device token
    disp_res = await async_client.post(
        "/api/v1/notifications/test-dispatch",
        json={
            "device_token": "ExponentPushToken[rejected_token_revoked_by_apns]",
            "notification_type": "SOS_ASSIGNMENT",
            "title": "Emergency Mission",
            "body": "Urgent rescue dispatch."
        }
    )
    assert disp_res.status_code == 200
    deliv = disp_res.json()["data"]

    # Verify status is strictly REJECTED_BY_PROVIDER
    assert deliv["status"] == "REJECTED_BY_PROVIDER"
    assert deliv["status"] != "SENT"
    assert deliv["status"] != "DISPATCHED"
    assert deliv["status"] != "DELIVERED"
    assert deliv["error_reason"] == "DeviceNotRegistered"
    assert deliv["dispatched_at"] is None
    assert deliv["delivered_at"] is None

    # 2. Verify in delivery audit log
    audit_res = await async_client.get("/api/v1/notifications/deliveries?status=REJECTED_BY_PROVIDER")
    assert audit_res.status_code == 200
    audit_items = audit_res.json()["data"]
    matched = next((i for i in audit_items if i["id"] == deliv["id"]), None)
    assert matched is not None
    assert matched["status"] == "REJECTED_BY_PROVIDER"


# ==============================================================================
# 7. NOTIFICATION ACK SECURITY MATRIX & IDENTITY PROTECTION
# ==============================================================================

@pytest.mark.asyncio
async def test_notification_ack_security_matrix(async_client: AsyncClient, test_db: AsyncSession):
    """
    Test ACK security matrix:
    1. Valid notification + correct user -> 200 OK
    2. Valid notification + wrong user -> 403 Forbidden
    3. Valid notification + no authentication / wrong credentials -> 403 Forbidden
    4. Invalid notification ID -> 404 Not Found
    """
    from backend.app.core.security import create_access_token

    # Setup 2 distinct users
    user_a = User(
        id=f"user_a_{uuid.uuid4().hex[:6]}",
        email=f"user_a_{uuid.uuid4().hex[:4]}@aegis.in",
        hashed_password="test_hash_pw",
        full_name="User A",
        role="citizen",
        is_active=True
    )
    user_b = User(
        id=f"user_b_{uuid.uuid4().hex[:6]}",
        email=f"user_b_{uuid.uuid4().hex[:4]}@aegis.in",
        hashed_password="test_hash_pw",
        full_name="User B",
        role="citizen",
        is_active=True
    )
    test_db.add(user_a)
    test_db.add(user_b)
    await test_db.commit()

    # Create notification delivery for User A
    notif_a = NotificationDeliveryRecord(
        id=f"notif-user-a-{uuid.uuid4().hex[:6]}",
        notification_type="SOS_STATUS",
        recipient_type="CITIZEN",
        recipient_id=user_a.id,
        device_token="ExponentPushToken[user_a_token]",
        channel="PUSH",
        title="SOS Status",
        body="Responder dispatched",
        data={"sos_id": "sos-123"},
        status="DISPATCHED",
        provider_response={"status": "ok"}
    )
    test_db.add(notif_a)
    await test_db.commit()

    token_a = create_access_token(user_a.id, role="citizen")
    token_b = create_access_token(user_b.id, role="citizen")

    # 1. Valid notification + correct user -> 200 OK
    res_correct = await async_client.post(
        f"/api/v1/notifications/{notif_a.id}/ack",
        json={"device_id": "dev_a", "client_timestamp": utc_now().isoformat()},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_correct.status_code == 200
    assert res_correct.json()["data"]["status"] == "DELIVERED"

    # Reset status back to DISPATCHED for negative tests
    notif_a.status = "DISPATCHED"
    await test_db.commit()

    # 2. Valid notification + wrong user -> 403 Forbidden
    res_wrong_user = await async_client.post(
        f"/api/v1/notifications/{notif_a.id}/ack",
        json={"device_id": "dev_b", "client_timestamp": utc_now().isoformat()},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_wrong_user.status_code == 403
    assert "Forbidden" in (res_wrong_user.json().get("error", {}).get("message") or res_wrong_user.json().get("detail", ""))

    # 3. Valid notification + no authentication / wrong credentials -> 403 Forbidden
    res_no_auth = await async_client.post(
        f"/api/v1/notifications/{notif_a.id}/ack",
        json={"device_id": "unknown_device", "client_timestamp": utc_now().isoformat()}
    )
    assert res_no_auth.status_code == 403

    # 4. Invalid notification ID -> 404 Not Found
    res_not_found = await async_client.post(
        "/api/v1/notifications/non-existent-notif-id-9999/ack",
        json={"device_id": "dev_a"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_not_found.status_code == 404


@pytest.mark.asyncio
async def test_authentication_identity_cannot_be_spoofed(async_client: AsyncClient, test_db: AsyncSession):
    """
    Test JWT identity precedence over X-Aegis-User-Id header:
    - Valid JWT + mismatched X-Aegis-User-Id: Authenticated user ID takes precedence
    """
    from backend.app.core.security import create_access_token

    user = User(
        id=f"legit_user_{uuid.uuid4().hex[:6]}",
        email=f"legit_{uuid.uuid4().hex[:4]}@aegis.in",
        hashed_password="test_hash_pw",
        full_name="Legit User",
        role="citizen",
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()

    valid_token = create_access_token(user.id, role="citizen")

    # 1. Valid JWT + wrong X-Aegis-User-Id spoof attempt -> Authenticated user's identity is used
    dev_id = f"test_device_spoof_{uuid.uuid4().hex[:4]}"
    res_spoof = await async_client.post(
        "/api/v1/notifications/tokens/register",
        json={
            "device_id": dev_id,
            "push_token": f"ExponentPushToken[{dev_id}]",
            "platform": "ANDROID"
        },
        headers={
            "Authorization": f"Bearer {valid_token}",
            "X-Aegis-User-Id": "spoofed_target_user_id"
        }
    )
    assert res_spoof.status_code == 200
    token_rec = (await test_db.execute(
        select(DeviceToken).where(DeviceToken.device_id == dev_id)
    )).scalars().first()
    assert token_rec is not None
    assert token_rec.user_id == user.id
    assert token_rec.user_id != "spoofed_target_user_id"
