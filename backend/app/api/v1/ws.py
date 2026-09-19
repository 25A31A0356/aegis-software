"""
AEGIS UNIFIED DATA CORE - Real-Time WebSocket Gateway
/api/v1/ws
Real-time bidirectional event channel for Aegis Web Portal & Aegis Alert Mobile App.
"""
from typing import Optional
import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.app.realtime.manager import manager
from backend.app.core.config import settings
from backend.app.utils.logger import logger

router = APIRouter(tags=["Real-Time WebSockets"])


@router.websocket("/ws")
async def websocket_event_gateway(
    websocket: WebSocket,
    client: Optional[str] = Query(default="web", description="Client identifier (web or app)"),
    client_key: Optional[str] = Query(default=None, description="Client API verification key"),
    token: Optional[str] = Query(default=None, description="Optional JWT bearer token")
):
    """
    Real-Time WebSocket Gateway for Aegis Web & Mobile App.
    Receives instant push notifications for:
    - REPORT_CREATED, REPORT_UPDATED, REPORT_VERIFIED, REPORT_RESOLVED
    - HAZARD_CREATED, HAZARD_UPDATED
    - SOS_CREATED, SOS_UPDATED
    """
    # Accept connection
    client_type = (client or "web").lower()
    await manager.connect(
        websocket=websocket,
        client_type=client_type,
        client_key=client_key or "",
        user_id=None
    )

    # Send initial welcome & connection confirmation packet
    welcome_packet = {
        "event": "CONNECTED",
        "service": "AEGIS Real-Time Gateway",
        "version": settings.VERSION,
        "client_type": client_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "available_channels": ["all", "reports", "hazards", "sos"]
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
