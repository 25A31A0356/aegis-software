"""
AEGIS UNIFIED DATA CORE - Real-Time Event Broker & WebSocket/SSE/Redis Streams Manager
Coordinates live synchronization across Aegis Web (Portal) and Aegis Alert App (Mobile).
Features:
- WebSocket connection manager with client metadata & RBAC channel authorization
- Heartbeat ping/pong monitor & stale socket cleanup
- Schema versioning (v1.0.0) with deduplication filter
- Redis Pub/Sub multi-instance broadcast + Redis Streams durable replay
- In-memory circular replay buffer fallback
"""
import asyncio
import json
import uuid
import time
from collections import deque
from typing import Dict, Set, List, Any, Optional, Tuple
from datetime import datetime, timezone
from fastapi import WebSocket
from backend.app.cache.redis_client import CacheManager
from backend.app.utils.logger import logger

EVENT_SCHEMA_VERSION = "1.0.0"


class ConnectionManager:
    """
    Thread/Async-safe WebSocket Connection & Channel Subscription Manager with RBAC authorization.
    """
    def __init__(self):
        # Maps websocket -> {client_type, client_key, user_id, role, connected_at, last_heartbeat, subscriptions}
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        # SSE listener queues
        self.sse_listeners: Set[asyncio.Queue] = set()
        # Deduplication filter (event_id -> insertion_time)
        self._seen_events: deque = deque(maxlen=5000)
        self._seen_set: Set[str] = set()
        # In-memory circular replay buffer
        self._replay_buffer: deque = deque(maxlen=1000)
        # Background task handle for cross-instance listener
        self._redis_sub_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(
        self,
        websocket: WebSocket,
        client_type: str = "web",
        client_key: str = "",
        user_id: Optional[str] = None,
        role: str = "public"
    ):
        await websocket.accept()
        now_iso = datetime.now(timezone.utc).isoformat()
        now_ts = time.time()
        self.active_connections[websocket] = {
            "client_type": client_type,
            "client_key": client_key,
            "user_id": user_id,
            "role": role or "public",
            "connected_at": now_iso,
            "last_heartbeat": now_ts,
            "subscriptions": {"all", "reports", "hazards", "sos", "alerts"}
        }
        logger.info(f"WebSocket client connected: type={client_type}, user={user_id or 'anon'}, role={role}, total_active={len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            meta = self.active_connections.pop(websocket)
            logger.info(f"WebSocket client disconnected: type={meta.get('client_type')}, user={meta.get('user_id')}, remaining={len(self.active_connections)}")

    def record_heartbeat(self, websocket: WebSocket):
        """Updates last received heartbeat timestamp for a socket."""
        if websocket in self.active_connections:
            self.active_connections[websocket]["last_heartbeat"] = time.time()

    def is_channel_authorized(self, websocket: WebSocket, channel: str) -> Tuple[bool, str]:
        """
        Validates whether a client is authorized to subscribe to a given channel.
        """
        if websocket not in self.active_connections:
            return False, "Unregistered connection."

        meta = self.active_connections[websocket]
        user_id = meta.get("user_id")
        role = meta.get("role", "public")
        ch = (channel or "").lower().strip()

        # Public broadcast channels
        if ch in ("all", "reports", "hazards", "alerts", "sos"):
            return True, "Authorized public channel."

        # User-specific private channel
        if ch.startswith("user:"):
            target_user = ch.split("user:", 1)[1]
            if user_id and (user_id == target_user or role in ("admin", "official")):
                return True, "Authorized user personal channel."
            return False, "Forbidden: cannot subscribe to another user's personal channel."

        # Specific SOS incident channel
        if ch.startswith("sos:"):
            # Authorized for authenticated users, responders, and officials
            if role in ("admin", "official", "sdrf_officer", "responder") or user_id:
                return True, "Authorized SOS tracking channel."
            return False, "Authentication required for targeted SOS incident channel."

        # Privileged control room / admin channels
        if ch in ("control_room", "admin:events", "admin:alerts"):
            if role in ("admin", "official", "sdrf_officer"):
                return True, "Authorized privileged channel."
            return False, "Forbidden: Administrator or Emergency Officer role required."

        # Default allowed for standard names
        return True, "Authorized."

    def subscribe(self, websocket: WebSocket, channel: str) -> Tuple[bool, str]:
        """Subscribes websocket to a channel with authorization verification."""
        auth_ok, reason = self.is_channel_authorized(websocket, channel)
        if not auth_ok:
            return False, reason

        if websocket in self.active_connections:
            self.active_connections[websocket]["subscriptions"].add(channel.lower().strip())
            return True, f"Subscribed to '{channel}'."
        return False, "Connection not active."

    def unsubscribe(self, websocket: WebSocket, channel: str):
        if websocket in self.active_connections:
            self.active_connections[websocket]["subscriptions"].discard(channel.lower().strip())

    async def broadcast_ws(self, message: Dict[str, Any], channel: str = "all"):
        """Broadcasts structured event to all active WebSockets subscribed to channel."""
        disconnected = []
        text_payload = json.dumps(message)
        channel_clean = channel.lower().strip()

        for ws, meta in list(self.active_connections.items()):
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

        for ws, meta in list(self.active_connections.items()):
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

    # Replay Buffer Management
    def record_event_for_replay(self, event_packet: Dict[str, Any]):
        """Caches event in circular replay buffer."""
        evt_id = event_packet.get("id")
        if evt_id:
            if evt_id in self._seen_set:
                return
            self._seen_set.add(evt_id)
            self._seen_events.append(evt_id)
            if len(self._seen_set) > 6000:
                self._seen_set = set(self._seen_events)

        self._replay_buffer.append(event_packet)

    def is_duplicate(self, event_id: str) -> bool:
        """Checks if event was already processed."""
        if not event_id:
            return False
        return event_id in self._seen_set

    async def get_events_since(
        self,
        last_event_id: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieves missed events for reconnection replay.
        First attempts Redis Streams query (XRANGE), falls back to in-memory circular buffer.
        """
        events: List[Dict[str, Any]] = []
        ch_filter = channel.lower().strip() if channel else None

        # 1. Try Redis Streams if available
        try:
            r = await CacheManager.get_redis()
            if r:
                # Read stream from last_event_id or earliest
                start_id = f"({last_event_id}" if last_event_id and "-" in str(last_event_id) else "-"
                stream_items = await r.xrange("aegis:events:stream", min=start_id, count=limit)
                for item_id, item_data in stream_items:
                    payload_raw = item_data.get(b"payload") or item_data.get("payload")
                    if payload_raw:
                        if isinstance(payload_raw, bytes):
                            payload_raw = payload_raw.decode("utf-8")
                        evt = json.loads(payload_raw)
                        evt_ch = (evt.get("channel") or "").lower()
                        if not ch_filter or ch_filter == "all" or evt_ch == ch_filter or evt_ch == "all":
                            evt["stream_id"] = item_id if isinstance(item_id, str) else item_id.decode("utf-8")
                            events.append(evt)
                if events:
                    return events
        except Exception as e:
            logger.debug(f"Redis Streams replay query skipped: {e}")

        # 2. In-memory replay buffer fallback
        found_last = False if last_event_id else True
        for evt in list(self._replay_buffer):
            evt_id = evt.get("id")
            if not found_last:
                if evt_id == last_event_id:
                    found_last = True
                continue

            evt_ch = (evt.get("channel") or "").lower()
            if not ch_filter or ch_filter == "all" or evt_ch == ch_filter or evt_ch == "all":
                events.append(evt)
                if len(events) >= limit:
                    break

        return events

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

    async def cleanup_stale_connections(self, max_stale_seconds: float = 60.0):
        """Scans active connections and drops connections that exceeded heartbeat timeout."""
        now = time.time()
        stale = []
        for ws, meta in list(self.active_connections.items()):
            last_hb = meta.get("last_heartbeat", now)
            if (now - last_hb) > max_stale_seconds:
                stale.append(ws)

        for ws in stale:
            logger.info(f"Closing stale WebSocket connection (idle > {max_stale_seconds}s)")
            try:
                await ws.close(code=1000, reason="Heartbeat timeout")
            except Exception:
                pass
            self.disconnect(ws)


# Global connection manager singleton
manager = ConnectionManager()


class EventBroker:
    """
    High-level Distributed Event Broker.
    Coordinates local WebSocket fanout, SSE feeds, Redis Pub/Sub multi-instance broadcast,
    and Redis Streams durable replay append.
    """
    _sequence_counter: int = 0

    @staticmethod
    def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Strictly redacts private user fields before public streaming."""
        clean = dict(payload)
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
        category: str = "GENERAL"
    ) -> Dict[str, Any]:
        """
        Dispatches real-time event across:
        1. Local connected WebSockets (Web + Mobile)
        2. Local SSE streaming connections
        3. In-memory replay buffer
        4. Distributed Redis PubSub channel (aegis:realtime:events)
        5. Durable Redis Streams append-only log (aegis:events:stream)
        """
        cls._sequence_counter += 1
        event_id = f"evt_{uuid.uuid4().hex}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Build standardized v1.0.0 envelope
        sanitized_data = cls.sanitize_payload(data)
        event_packet = {
            "id": event_id,
            "version": EVENT_SCHEMA_VERSION,
            "event": event_type,
            "category": category,
            "channel": channel,
            "timestamp": now_iso,
            "sequence": cls._sequence_counter,
            "data": sanitized_data,
            "metadata": {
                "producer": "aegis-unified-core",
                "environment": "production"
            }
        }

        # Record in local deduplication and replay buffer
        manager.record_event_for_replay(event_packet)

        # 1. Local WebSocket Broadcast
        await manager.broadcast_ws(event_packet, channel=channel)

        # 2. Local SSE Stream Broadcast
        await manager.broadcast_sse(event_packet)

        # 3. Redis Multi-Instance Pub/Sub & Durable Streams Append
        try:
            r = await CacheManager.get_redis()
            if r:
                serialized = json.dumps(event_packet)
                # Redis Pub/Sub (Cross-worker multi-node fanout)
                await r.publish("aegis:realtime:events", serialized)
                # Redis Streams (Durable replay log with maxlen=10000)
                await r.xadd(
                    "aegis:events:stream",
                    {
                        "event_id": event_id,
                        "event_type": event_type,
                        "channel": channel,
                        "payload": serialized
                    },
                    maxlen=10000,
                    approximate=True
                )
        except Exception as e:
            logger.debug(f"Redis PubSub/Streams broadcast skipped: {e}")

        logger.info(f"Broadcasted real-time event '{event_type}' (id={event_id}) on channel '{channel}' to Web & App.")
        return event_packet
