"""
AEGIS UNIFIED DATA CORE - Real-Time WebSocket Gateway
/api/v1/ws and /api/v1/ws/sos
Real-time bidirectional event channel for Aegis Web Portal & Aegis Alert Mobile App.
"""
from typing import Optional
import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.app.realtime.manager import manager
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
    initial_channel: Optional[str] = None
):
    """Core WebSocket connection lifecycle handler."""
    client_type = (client or "web").lower()
    
    # 1. Resolve User ID from token if provided, or client_id
    user_id: Optional[str] = client_id
    if token:
        try:
            payload = decode_token(token)
            if payload and "sub" in payload:
                user_id = str(payload["sub"])
        except Exception:
            pass

    # 2. Connect
    await manager.connect(
        websocket=websocket,
        client_type=client_type,
        client_key=client_key or "",
        user_id=user_id
    )

    # 3. Auto-subscribe to base channels and personal user channel
    if user_id:
        manager.subscribe(websocket, f"user:{user_id}")
    if initial_channel:
        manager.subscribe(websocket, initial_channel)

    # 4. Send initial welcome packet
    available_channels = ["all", "reports", "hazards", "sos"]
    if user_id:
        available_channels.append(f"user:{user_id}")
    if initial_channel:
        available_channels.append(initial_channel)

    welcome_packet = {
        "event": "CONNECTED",
        "service": "AEGIS Real-Time Gateway",
        "version": settings.VERSION,
        "client_type": client_type,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "available_channels": available_channels
    }
    await websocket.send_text(json.dumps(welcome_packet))

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                msg_type = msg.get("type", "").lower()

                if msg_type == "ping":
                    pong = {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}
                    await websocket.send_text(json.dumps(pong))

                elif msg_type == "subscribe":
                    channel = msg.get("channel", "all")
                    manager.subscribe(websocket, channel)
                    ack = {"type": "subscribed", "channel": channel, "timestamp": datetime.now(timezone.utc).isoformat()}
                    await websocket.send_text(json.dumps(ack))

                elif msg_type == "unsubscribe":
                    channel = msg.get("channel", "all")
                    manager.unsubscribe(websocket, channel)
                    ack = {"type": "unsubscribed", "channel": channel, "timestamp": datetime.now(timezone.utc).isoformat()}
                    await websocket.send_text(json.dumps(ack))

                else:
                    logger.debug(f"Received WebSocket message: {msg}")

            except json.JSONDecodeError:
                err = {"error": "Invalid JSON format", "timestamp": datetime.now(timezone.utc).isoformat()}
                await websocket.send_text(json.dumps(err))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket connection error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws")
async def websocket_event_gateway(
    websocket: WebSocket,
    client: Optional[str] = Query(default="web", description="Client identifier (web or app)"),
    client_key: Optional[str] = Query(default=None, description="Client API verification key"),
    client_id: Optional[str] = Query(default=None, description="Client/Device/User identifier"),
    token: Optional[str] = Query(default=None, description="Optional JWT bearer token")
):
    """
    Main Real-Time WebSocket Gateway for Aegis Web & Mobile App.
    """
    await _handle_websocket_session(
        websocket=websocket,
        client=client,
        client_key=client_key,
        client_id=client_id,
        token=token
    )


@router.websocket("/ws/sos")
async def websocket_sos_gateway(
    websocket: WebSocket,
    client: Optional[str] = Query(default="app", description="Client identifier (web or app)"),
    client_key: Optional[str] = Query(default=None, description="Client API verification key"),
    client_id: Optional[str] = Query(default=None, description="Client/Device/User identifier"),
    token: Optional[str] = Query(default=None, description="Optional JWT bearer token"),
    sos_id: Optional[str] = Query(default=None, description="Optional specific SOS Incident ID to track")
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
        initial_channel=initial_ch
    )

