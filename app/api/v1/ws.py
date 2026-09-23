"""
AEGIS UNIFIED DATA CORE - Real-Time WebSocket Gateway
/api/v1/ws and /api/v1/ws/sos
Real-time bidirectional event channel for Aegis Web Portal & Aegis Alert Mobile App.
Includes:
- Bearer JWT & client verification
- RBAC channel subscription authorization
- Heartbeat ping/pong and keepalive
- Missed event replay on reconnection via Redis Streams / circular buffer
"""
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.app.realtime.manager import manager, EVENT_SCHEMA_VERSION
from backend.app.core.config import settings
from backend.app.core.security import decode_token
from backend.app.utils.logger import logger

router = APIRouter(tags=["Real-Time WebSockets"])


async def _handle_websocket_session(
    websocket: WebSocket,
    client: Optional[str] = "web",
    client_key: Optional[str] = None,
    client_id: Optional[str] = None,
    token: Optional[str] = None,
    initial_channel: Optional[str] = None,
    last_event_id: Optional[str] = None
):
    """Core WebSocket connection lifecycle handler."""
    client_type = (client or "web").lower()
    
    # 1. Resolve User ID and Role from token if provided, or fallback to client_id
    user_id: Optional[str] = client_id
    role: str = "public"
    if token:
        try:
            payload = decode_token(token)
            if payload:
                user_id = str(payload.get("sub") or user_id or "")
                role = str(payload.get("role") or "public")
        except Exception as e:
            logger.debug(f"Token decoding in WebSocket handshake: {e}")

    # 2. Accept & Register connection
    await manager.connect(
        websocket=websocket,
        client_type=client_type,
        client_key=client_key or "",
        user_id=user_id,
        role=role
    )

    # 3. Auto-subscribe to base channels and personal user channel
    if user_id:
        manager.subscribe(websocket, f"user:{user_id}")
    if initial_channel:
        manager.subscribe(websocket, initial_channel)

    # 4. Available channels list for client discovery
    available_channels = ["all", "reports", "hazards", "sos", "alerts"]
    if user_id:
        available_channels.append(f"user:{user_id}")
    if initial_channel and initial_channel not in available_channels:
        available_channels.append(initial_channel)

    # 5. Send initial welcome packet
    welcome_packet = {
        "event": "CONNECTED",
        "service": "AEGIS Real-Time Event Gateway",
        "version": settings.VERSION,
        "schema_version": EVENT_SCHEMA_VERSION,
        "client_type": client_type,
        "user_id": user_id,
        "role": role,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "available_channels": available_channels
    }
    await websocket.send_text(json.dumps(welcome_packet))

    # 6. Replay missed events if client supplied last_event_id
    if last_event_id:
        try:
            missed_events = await manager.get_events_since(
                last_event_id=last_event_id,
                channel=initial_channel,
                limit=50
            )
            if missed_events:
                replay_packet = {
                    "type": "replay_batch",
                    "count": len(missed_events),
                    "since_id": last_event_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "events": missed_events
                }
                await websocket.send_text(json.dumps(replay_packet))
        except Exception as e:
            logger.warning(f"Error during initial event replay: {e}")

    # 7. Main message receiver loop
    try:
        while True:
            raw_text = await websocket.receive_text()
            manager.record_heartbeat(websocket)

            try:
                msg = json.loads(raw_text)
                msg_type = (msg.get("type") or msg.get("event") or "").lower()

                # A. Heartbeat Ping / Pong
                if msg_type in ("ping", "heartbeat"):
                    pong = {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "client_timestamp": msg.get("timestamp")
                    }
                    await websocket.send_text(json.dumps(pong))

                # B. Channel Subscription with RBAC
                elif msg_type == "subscribe":
                    target_channel = msg.get("channel", "all")
                    ok, reason = manager.subscribe(websocket, target_channel)
                    if ok:
                        ack = {
                            "type": "subscribed",
                            "channel": target_channel,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    else:
                        ack = {
                            "type": "subscription_denied",
                            "channel": target_channel,
                            "reason": reason,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    await websocket.send_text(json.dumps(ack))

                # C. Channel Unsubscription
                elif msg_type == "unsubscribe":
                    target_channel = msg.get("channel", "all")
                    manager.unsubscribe(websocket, target_channel)
                    ack = {
                        "type": "unsubscribed",
                        "channel": target_channel,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    await websocket.send_text(json.dumps(ack))

                # D. Replay Request
                elif msg_type == "replay":
                    req_last_id = msg.get("last_event_id") or msg.get("since_id")
                    req_ch = msg.get("channel")
                    events = await manager.get_events_since(
                        last_event_id=req_last_id,
                        channel=req_ch,
                        limit=msg.get("limit", 50)
                    )
                    replay_ack = {
                        "type": "replay_batch",
                        "count": len(events),
                        "since_id": req_last_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "events": events
                    }
                    await websocket.send_text(json.dumps(replay_ack))

                else:
                    logger.debug(f"Received custom WebSocket message from {user_id or client_type}: {msg}")

            except json.JSONDecodeError:
                err = {
                    "error": "Invalid JSON format",
                    "code": "MALFORMED_FRAME",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_text(json.dumps(err))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket connection closed with error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws")
async def websocket_event_gateway(
    websocket: WebSocket,
    client: Optional[str] = Query(default="web", description="Client identifier (web or app)"),
    client_key: Optional[str] = Query(default=None, description="Client API verification key"),
    client_id: Optional[str] = Query(default=None, description="Client/Device/User identifier"),
    token: Optional[str] = Query(default=None, description="Optional JWT bearer token"),
    last_event_id: Optional[str] = Query(default=None, description="Optional last processed event ID for missed event replay")
):
    """
    Main Real-Time WebSocket Gateway for Aegis Web & Mobile App.
    """
    await _handle_websocket_session(
        websocket=websocket,
        client=client,
        client_key=client_key,
        client_id=client_id,
        token=token,
        last_event_id=last_event_id
    )


@router.websocket("/ws/sos")
async def websocket_sos_gateway(
    websocket: WebSocket,
    client: Optional[str] = Query(default="app", description="Client identifier (web or app)"),
    client_key: Optional[str] = Query(default=None, description="Client API verification key"),
    client_id: Optional[str] = Query(default=None, description="Client/Device/User identifier"),
    token: Optional[str] = Query(default=None, description="Optional JWT bearer token"),
    sos_id: Optional[str] = Query(default=None, description="Optional specific SOS Incident ID to track"),
    last_event_id: Optional[str] = Query(default=None, description="Optional last processed event ID for replay")
):
    """
    Dedicated Real-Time SOS Responder & Incident Tracking WebSocket Gateway.
    """
    initial_ch = f"sos:{sos_id}" if sos_id else "sos"
    await _handle_websocket_session(
        websocket=websocket,
        client=client,
        client_key=client_key,
        client_id=client_id,
        token=token,
        initial_channel=initial_ch,
        last_event_id=last_event_id
    )


@router.get("/events")
@router.get("/realtime")
async def sse_realtime_stream():
    """
    Server-Sent Events (SSE) stream for realtime alerts, reports, and SOS dispatch.
    """
    import asyncio
    from fastapi.responses import StreamingResponse

    async def event_generator():
        q = await manager.add_sse_listener()
        try:
            # Handshake
            init_msg = json.dumps({
                "type": "SYSTEM_CONNECTED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"status": "LIVE", "channels": ["all", "reports", "hazards", "sos", "alerts"]}
            })
            yield f"data: {init_msg}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    hb = json.dumps({
                        "type": "SYSTEM_HEARTBEAT",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {}
                    })
                    yield f"data: {hb}\n\n"
        finally:
            manager.remove_sse_listener(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
