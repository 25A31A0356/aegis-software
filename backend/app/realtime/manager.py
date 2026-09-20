"""
AEGIS UNIFIED DATA CORE - Real-Time Event Broker & WebSocket/SSE Manager
Coordinates live synchronization across Aegis Web (Portal) and Aegis App (Mobile).
"""
import asyncio
import json
from typing import Dict, Set, Any, Optional
from datetime import datetime, timezone
from fastapi import WebSocket
from backend.app.cache.redis_client import CacheManager
from backend.app.utils.logger import logger


class ConnectionManager:
    """
    Manages active WebSocket client connections, channel subscriptions, and broadcasting.
    """
    def __init__(self):
        # Maps websocket instance to metadata dict: {"client_type": "web"|"app", "subscriptions": set()}
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        # SSE listener queues
        self.sse_listeners: Set[asyncio.Queue] = set()

    async def connect(
        self,
        websocket: WebSocket,
        client_type: str = "web",
        client_key: str = "",
        user_id: Optional[str] = None
    ):
        await websocket.accept()
        self.active_connections[websocket] = {
            "client_type": client_type,
            "client_key": client_key,
            "user_id": user_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "subscriptions": {"all", "reports", "hazards", "sos"}
        }
        logger.info(f"WebSocket client connected: type={client_type}, user={user_id or 'anon'}, total_active={len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            meta = self.active_connections.pop(websocket)
            logger.info(f"WebSocket client disconnected: type={meta.get('client_type')}, remaining={len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, channel: str):
        if websocket in self.active_connections:
            self.active_connections[websocket]["subscriptions"].add(channel.lower())

    def unsubscribe(self, websocket: WebSocket, channel: str):
        if websocket in self.active_connections:
            self.active_connections[websocket]["subscriptions"].discard(channel.lower())

    async def broadcast_ws(self, message: Dict[str, Any], channel: str = "all"):
        """Broadcasts structured event to all active WebSockets subscribed to channel."""
        disconnected = []
        text_payload = json.dumps(message)
        channel_clean = channel.lower()

        for ws, meta in self.active_connections.items():
            subs = meta.get("subscriptions", set())
            if channel_clean == "all" or channel_clean in subs or "all" in subs:
                try:
                    await ws.send_text(text_payload)
                except Exception as e:
                    logger.warning(f"Error sending WebSocket message to client: {e}")
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Sends targeted real-time message directly to all sockets of a specific user."""
        if not user_id:
            return False
        
        target_uid = str(user_id).strip()
        sent = False
        disconnected = []
        text_payload = json.dumps(message)

        for ws, meta in self.active_connections.items():
            if str(meta.get("user_id") or "") == target_uid:
                try:
                    await ws.send_text(text_payload)
                    sent = True
                except Exception as e:
                    logger.warning(f"Error sending direct WebSocket to user {user_id}: {e}")
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)
        return sent

    # SSE support
    async def add_sse_listener(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.sse_listeners.add(q)
        return q

    def remove_sse_listener(self, q: asyncio.Queue):
        self.sse_listeners.discard(q)

    async def broadcast_sse(self, message: Dict[str, Any]):
        """Pushes event to all active SSE streaming queues."""
        dead_queues = set()
        for q in list(self.sse_listeners):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(message)
            except Exception as e:
                logger.warning(f"Error pushing to SSE queue: {e}")
                dead_queues.add(q)

        for dq in dead_queues:
            self.remove_sse_listener(dq)


# Global connection manager singleton
manager = ConnectionManager()


class EventBroker:
    """
    High-level Event Broker for dispatching sanitized events to Web, Mobile, and Redis PubSub.
    """
    @staticmethod
    def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Strictly redacts any private user personal data before public streaming."""
        clean = dict(payload)
        # Redact private fields
        for field in ["caller_phone", "phone", "email", "hashed_password", "user_id", "encrypted_api_key"]:
            if field in clean:
                clean.pop(field, None)
        return clean

    @classmethod
    async def publish_event(
        cls,
        event_type: str,
        data: Dict[str, Any],
        channel: str = "all",
        category: str = "COMMUNITY_REPORT"
    ):
        """
        Dispatches real-time event across:
        1. Local connected WebSockets (Web + App)
        2. Local SSE streaming connections
        3. Distributed Redis PubSub channel
        """
        sanitized_data = cls.sanitize_payload(data)
        event_packet = {
            "event": event_type,
            "category": category,
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": sanitized_data
        }

        # 1. Broadcast to WebSockets
        await manager.broadcast_ws(event_packet, channel=channel)

        # 2. Broadcast to SSE streams
        await manager.broadcast_sse(event_packet)

        # 3. Publish to Redis if available
        try:
            r = await CacheManager.get_redis()
            if r:
                await r.publish("aegis:realtime:events", json.dumps(event_packet))
        except Exception as e:
            logger.debug(f"Redis pubsub publish skipped: {e}")

        logger.info(f"Broadcasted real-time event '{event_type}' on channel '{channel}' to Web & App clients.")
