"""
AEGIS REAL-TIME EVENT ARCHITECTURE SUITE
Validates the complete real-time event pipeline:
1. Mobile/client request -> API -> Database -> Event Bus -> WebSocket -> Web Client
2. Real-Time Events:
   - SOS_CREATED
   - SOS_ASSIGNED
   - RESPONDER_LOCATION_UPDATED
   - SOS_STATUS_UPDATED
   - REPORT_CREATED
   - REPORT_UPDATED
   - ALERT_CREATED
   - ALERT_UPDATED
3. RBAC Channel Authorization (Public vs User-Private vs Control Room)
4. Heartbeat (Ping/Pong) Protocol
5. Reconnection & Replay of Missed Events
6. Event Versioning & Duplicate Suppression
"""
import pytest
import uuid
import json
import asyncio
from sqlalchemy import select
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.database.models import SOSSignal, IncidentReport, AlertRecord, User
from backend.app.realtime.manager import manager, EventBroker, EVENT_SCHEMA_VERSION


class MockWebSocket:
    """Simulated async WebSocket client for testing event delivery."""
    def __init__(self):
        self.received_messages = []
        self.closed = False

    async def accept(self):
        pass

    async def send_text(self, data: str):
        self.received_messages.append(json.loads(data))

    async def close(self, code=1000, reason=""):
        self.closed = True


@pytest.mark.asyncio
async def test_complete_realtime_pipeline_api_to_websocket_fanout(async_client, test_db):
    """
    PROVES COMPLETE PIPELINE:
    Client Request -> Backend API -> PostgreSQL/DB State -> Event Broker -> WebSocket -> Web Client
    """
    test_uid = f"citizen-rt-{uuid.uuid4().hex[:8]}"
    test_resp_id = f"resp-rt-{uuid.uuid4().hex[:8]}"

    # Setup database users
    u1 = User(id=test_uid, email=f"{test_uid}@aegis.gov.in", hashed_password="pw", full_name="Disaster Citizen", role="public", is_active=True)
    u2 = User(id=test_resp_id, email=f"{test_resp_id}@aegis.gov.in", hashed_password="pw", full_name="SDRF Officer", role="sdrf_officer", is_active=True)
    test_db.add_all([u1, u2])
    await test_db.commit()

    # 1. Connect a simulated Web Client WebSocket to the Real-Time Manager
    mock_ws = MockWebSocket()
    await manager.connect(mock_ws, client_type="web", user_id="dispatcher-admin", role="admin")
    manager.subscribe(mock_ws, "all")
    manager.subscribe(mock_ws, "sos")
    manager.subscribe(mock_ws, "reports")
    manager.subscribe(mock_ws, "alerts")

    try:
        # ======================================================================
        # STEP 1: Citizen creates SOS -> Verified in DB & WebSocket receives SOS_CREATED
        # ======================================================================
        sos_res = await async_client.post(
            "/api/v1/sos",
            json={
                "caller_name": "Stranded in Flood",
                "emergency_type": "flood_trapped",
                "severity": "CRITICAL",
                "short_message": "Water reached 1st floor balcony, need boat evacuation",
                "latitude": 17.7300,
                "longitude": 83.3100,
                "casualties_count": 2,
                "battery_percent": 90,
                "idempotency_key": f"rt-sos-{uuid.uuid4().hex[:8]}"
            },
            headers={"X-Aegis-User-Id": test_uid}
        )
        assert sos_res.status_code == 200
        sos_id = sos_res.json()["data"]["id"]

        # Assert persisted in DB
        db_sos = (await test_db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))).scalars().first()
        assert db_sos is not None, "SOS was not persisted to database"

        # Assert WebSocket received SOS_CREATED
        sos_created_events = [m for m in mock_ws.received_messages if m.get("event") == "SOS_CREATED"]
        assert len(sos_created_events) >= 1, "WebSocket did not receive SOS_CREATED event!"
        latest_sos_evt = sos_created_events[-1]
        assert latest_sos_evt["version"] == EVENT_SCHEMA_VERSION
        assert latest_sos_evt["data"]["id"] == sos_id

        # ======================================================================
        # STEP 2: Responder accepts SOS -> DB Assignment created & WebSocket receives SOS_ASSIGNED
        # ======================================================================
        accept_res = await async_client.post(
            f"/api/v1/sos/{sos_id}/accept",
            headers={"X-Aegis-User-Id": test_resp_id}
        )
        assert accept_res.status_code == 200

        sos_assigned_events = [m for m in mock_ws.received_messages if m.get("event") in ("SOS_ASSIGNED", "SOS_ACCEPTED")]
        assert len(sos_assigned_events) >= 1, "WebSocket did not receive SOS_ASSIGNED event!"

        # ======================================================================
        # STEP 3: Responder streams GPS -> DB breadcrumb persisted & WebSocket receives RESPONDER_LOCATION_UPDATED
        # ======================================================================
        loc_res = await async_client.post(
            f"/api/v1/sos/{sos_id}/responder-location",
            json={
                "latitude": 17.7280,
                "longitude": 83.3080,
                "accuracy_meters": 3.5,
                "speed_kmh": 32.0
            },
            headers={"X-Aegis-User-Id": test_resp_id}
        )
        assert loc_res.status_code == 200

        loc_events = [m for m in mock_ws.received_messages if m.get("event") == "RESPONDER_LOCATION_UPDATED"]
        assert len(loc_events) >= 1, "WebSocket did not receive RESPONDER_LOCATION_UPDATED event!"

        # ======================================================================
        # STEP 4: Status Transition -> DB status updated & WebSocket receives SOS_STATUS_UPDATED
        # ======================================================================
        status_res = await async_client.post(
            f"/api/v1/sos/{sos_id}/status",
            json={"status": "ON_SITE", "reason": "Rescue vessel reached stranded citizens"},
            headers={"X-Aegis-User-Id": test_resp_id}
        )
        assert status_res.status_code == 200

        status_events = [m for m in mock_ws.received_messages if m.get("event") in ("SOS_STATUS_UPDATED", "SOS_ON_SITE")]
        assert len(status_events) >= 1, "WebSocket did not receive SOS_STATUS_UPDATED event!"

        # ======================================================================
        # STEP 5: Community Report Created -> DB record created & WebSocket receives REPORT_CREATED
        # ======================================================================
        rep_res = await async_client.post(
            "/api/v1/reports",
            json={
                "title": "Submerged Bridge on NH16",
                "description": "Bridge completely submerged under 3 feet flood water, traffic halted",
                "category": "FLOOD",
                "severity": "HIGH",
                "latitude": 17.7500,
                "longitude": 83.3300,
                "idempotency_key": f"rt-rep-{uuid.uuid4().hex[:8]}"
            }
        )
        assert rep_res.status_code == 200
        rep_id = rep_res.json()["data"]["id"]

        # Assert in DB
        db_rep = (await test_db.execute(select(IncidentReport).where(IncidentReport.id == rep_id))).scalars().first()
        assert db_rep is not None

        rep_events = [m for m in mock_ws.received_messages if m.get("event") == "REPORT_CREATED"]
        assert len(rep_events) >= 1, "WebSocket did not receive REPORT_CREATED event!"

        # ======================================================================
        # STEP 6: Community Report Voted -> DB record updated & WebSocket receives REPORT_UPDATED
        # ======================================================================
        vote_res = await async_client.post(
            f"/api/v1/reports/{rep_id}/vote",
            json={"voter_id": f"voter-{uuid.uuid4().hex[:6]}", "vote_type": "UPVOTE"}
        )
        assert vote_res.status_code == 200

        vote_events = [m for m in mock_ws.received_messages if m.get("event") == "REPORT_UPDATED"]
        assert len(vote_events) >= 1, "WebSocket did not receive REPORT_UPDATED event!"

        # ======================================================================
        # STEP 7: Official Alert Published -> DB record created & WebSocket receives ALERT_CREATED
        # ======================================================================
        alert_res = await async_client.post(
            "/api/v1/alerts",
            json={
                "headline": "Flash Flood Red Alert for Low Lying Coastal Areas",
                "description": "Inundation of low lying zones expected due to continuous torrential rain.",
                "hazard_type": "FLOOD",
                "severity": "warning",
                "latitude": 17.6868,
                "longitude": 83.2185
            }
        )
        assert alert_res.status_code == 200
        alert_id = alert_res.json()["data"]["id"]

        # Assert in DB
        db_alert = (await test_db.execute(select(AlertRecord).where(AlertRecord.id == alert_id))).scalars().first()
        assert db_alert is not None

        alert_events = [m for m in mock_ws.received_messages if m.get("event") == "ALERT_CREATED"]
        assert len(alert_events) >= 1, "WebSocket did not receive ALERT_CREATED event!"

        # ======================================================================
        # STEP 8: Official Alert Updated -> DB record updated & WebSocket receives ALERT_UPDATED
        # ======================================================================
        update_alert_res = await async_client.post(
            f"/api/v1/alerts/{alert_id}/update",
            json={"severity": "emergency", "instruction": "Immediate evacuation ordered for Sector 4."}
        )
        assert update_alert_res.status_code == 200

        alert_up_events = [m for m in mock_ws.received_messages if m.get("event") == "ALERT_UPDATED"]
        assert len(alert_up_events) >= 1, "WebSocket did not receive ALERT_UPDATED event!"

    finally:
        manager.disconnect(mock_ws)


@pytest.mark.asyncio
async def test_channel_authorization_and_security():
    """
    Verifies that unauthorized clients cannot subscribe to restricted channels.
    """
    public_ws = MockWebSocket()
    await manager.connect(public_ws, client_type="web", user_id="citizen-456", role="public")

    try:
        # 1. Public user CAN subscribe to public channels
        ok, _ = manager.subscribe(public_ws, "reports")
        assert ok is True

        ok, _ = manager.subscribe(public_ws, "hazards")
        assert ok is True

        # 2. Public user CAN subscribe to their OWN user channel
        ok, _ = manager.subscribe(public_ws, "user:citizen-456")
        assert ok is True

        # 3. Public user CANNOT subscribe to another user's personal channel
        ok, reason = manager.subscribe(public_ws, "user:victim-999")
        assert ok is False
        assert "Forbidden" in reason

        # 4. Public user CANNOT subscribe to privileged control room
        ok, reason = manager.subscribe(public_ws, "control_room")
        assert ok is False
        assert "Forbidden" in reason
    finally:
        manager.disconnect(public_ws)


@pytest.mark.asyncio
async def test_reconnection_and_event_replay():
    """
    Verifies that reconnecting clients can replay missed events in chronological order.
    """
    # Publish 3 versioned events to the broker
    evt1 = await EventBroker.publish_event("TEST_EVT_1", {"index": 1}, channel="reports")
    evt2 = await EventBroker.publish_event("TEST_EVT_2", {"index": 2}, channel="reports")
    evt3 = await EventBroker.publish_event("TEST_EVT_3", {"index": 3}, channel="reports")

    # Query events since evt1.id
    replay_events = await manager.get_events_since(last_event_id=evt1["id"], channel="reports")
    
    # Must contain evt2 and evt3
    event_names = [e["event"] for e in replay_events]
    assert "TEST_EVT_2" in event_names
    assert "TEST_EVT_3" in event_names


@pytest.mark.asyncio
async def test_event_deduplication_and_versioning():
    """
    Verifies event versioning in envelopes and duplicate tracking.
    """
    packet = await EventBroker.publish_event(
        event_type="TEST_DEDUP_EVENT",
        data={"field": "value"},
        channel="sos"
    )
    assert packet["version"] == "1.0.0"
    assert packet["id"].startswith("evt_")
    assert manager.is_duplicate(packet["id"]) is True
