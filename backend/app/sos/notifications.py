"""
AEGIS UNIFIED DATA CORE - SOS Notification Delivery Subsystem
Abstracts dispatching across In-App WebSockets, Family Emergency Contacts (SMS/Alerts),
and Mobile Push Notification interfaces (FCM / APNs ready).
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.models import SOSSignal, SOSNotification, utc_now
from backend.app.realtime.manager import EventBroker, manager
from backend.app.utils.logger import logger


class BasePushAdapter:
    """Pluggable push notification adapter interface."""
    async def send_push(self, device_token: str, title: str, body: str, data: Dict[str, Any]) -> bool:
        # Default mock / log adapter for local development
        logger.info(f"[Push Notification] Sent to token={device_token[:8]}... title='{title}', body='{body}'")
        return True


class NotificationService:
    """
    Orchestrates multi-channel emergency distress notifications.
    """
    push_adapter: BasePushAdapter = BasePushAdapter()

    @classmethod
    async def notify_emergency_contacts(
        cls,
        db: AsyncSession,
        sos: SOSSignal,
        emergency_contacts: List[Dict[str, Any]]
    ) -> List[SOSNotification]:
        """
        Alerts registered family/emergency contacts with authorized distress coordinates and alert message.
        """
        notifications: List[SOSNotification] = []
        if not emergency_contacts:
            return notifications

        for contact in emergency_contacts:
            phone = contact.get("phone", "")
            name = contact.get("name", "Emergency Contact")
            relationship = contact.get("relationship", "Family")

            loc_desc = sos.address or (f"{sos.district}, {sos.state}" if sos.district else None) or f"{sos.latitude:.4f}, {sos.longitude:.4f}"
            alert_msg = f"Emergency SOS activated by {sos.caller_name}. Current location: {loc_desc}. Open AEGIS ALERT to view the live emergency location."
            details = {
                "contact_name": name,
                "contact_phone": phone,
                "relationship": relationship,
                "emergency_type": sos.emergency_type,
                "severity": sos.severity,
                "latitude": sos.latitude,
                "longitude": sos.longitude,
                "address": sos.address or sos.city or "Unknown Location",
                "message": alert_msg,
                "delivery_channel": "SMS",
                "delivery_timestamp": utc_now().isoformat()
            }

            notification = SOSNotification(
                sos_id=sos.id,
                recipient_type="FAMILY_CONTACT",
                recipient_id=phone or name,
                channel="SMS",
                status="SENT",
                details=details,
                sent_at=utc_now()
            )
            db.add(notification)
            notifications.append(notification)
            logger.info(f"Dispatched Emergency Alert to family contact '{name}' ({phone}) for SOS {sos.id}")

        await db.commit()
        return notifications

    @classmethod
    async def notify_nearby_responders(
        cls,
        db: AsyncSession,
        sos: SOSSignal,
        candidates: List[Dict[str, Any]]
    ) -> List[SOSNotification]:
        """
        Sends privacy-preserving, Rapido-like SOS offers to nearby eligible responders.
        Strictly excludes exact GPS coordinates and private phone numbers.
        """
        notifications: List[SOSNotification] = []
        if not candidates:
            return notifications

        for cand in candidates:
            user_id = cand["user_id"]
            dist_km = cand["distance_km"]

            # Sanitized Rapido-style offer payload
            offer_payload = {
                "sos_id": sos.id,
                "emergency_type": sos.emergency_type,
                "severity": sos.severity,
                "approximate_distance_km": dist_km,
                "approximate_area": sos.district or sos.city or sos.state or "Nearby Area",
                "short_message": sos.short_message or "Citizen requested urgent assistance",
                "requested_at": sos.created_at.isoformat() if sos.created_at else utc_now().isoformat(),
                "expires_in_seconds": 45
            }

            # 1. Send targeted real-time WebSocket notification to candidate
            await manager.send_to_user(user_id, {
                "event": "SOS_OFFERED",
                "category": "SOS",
                "timestamp": utc_now().isoformat(),
                "data": offer_payload
            })

            # 2. Record notification
            notification = SOSNotification(
                sos_id=sos.id,
                recipient_type="NEARBY_RESPONDER",
                recipient_id=user_id,
                channel="WEBSOCKET",
                status="SENT",
                details=offer_payload,
                sent_at=utc_now()
            )
            db.add(notification)
            notifications.append(notification)

        await db.commit()
        return notifications

    @classmethod
    async def notify_safe_event(
        cls,
        db: AsyncSession,
        safe_event: Any,
        emergency_contacts: List[Dict[str, Any]]
    ) -> List[SOSNotification]:
        """
        Alerts registered family/emergency contacts that the citizen has declared they are SAFE.
        """
        notifications: List[SOSNotification] = []
        if not emergency_contacts:
            return notifications

        for contact in emergency_contacts:
            phone = contact.get("phone", "")
            name = contact.get("name", "Emergency Contact")
            relationship = contact.get("relationship", "Family")

            details = {
                "contact_name": name,
                "contact_phone": phone,
                "relationship": relationship,
                "status": "SAFE",
                "latitude": safe_event.latitude,
                "longitude": safe_event.longitude,
                "location_name": safe_event.location_name or safe_event.district or safe_event.state or "Current Location",
                "message": f"SAFETY UPDATE: {safe_event.user_name} is SAFE. Location: {safe_event.location_name or safe_event.district or 'Current Location'}. Message: {safe_event.message}"
            }

            notification = SOSNotification(
                sos_id=safe_event.sos_id or safe_event.id,
                recipient_type="FAMILY_CONTACT",
                recipient_id=phone or name,
                channel="SMS",
                status="SENT",
                details=details,
                sent_at=utc_now()
            )
            db.add(notification)
            notifications.append(notification)
            logger.info(f"Dispatched SAFE status notification to '{name}' ({phone}) for SafeEvent {safe_event.id}")

        await db.commit()
        return notifications

    @classmethod
    async def broadcast_sos_event(
        cls,
        event_name: str,
        sos: SOSSignal,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Broadcasts authorized event payloads to relevant participants:
        - General public/operators: Sanitized general event
        - Channel `sos:{sos_id}`: Detailed event for assigned participants
        - Direct user socket for requester and assigned responder
        """
        base_data = {
            "id": sos.id,
            "sos_id": sos.id,
            "status": sos.status,
            "emergency_type": sos.emergency_type,
            "severity": sos.severity,
            "city": sos.city,
            "district": sos.district,
            "state": sos.state,
            "created_at": sos.created_at.isoformat() if sos.created_at else "",
            "updated_at": sos.updated_at.isoformat() if sos.updated_at else "",
        }

        if extra_data:
            base_data.update(extra_data)

        # 1. Broadcast to general SOS channel (operators & maps)
        await EventBroker.publish_event(
            event_type=event_name,
            data=base_data,
            channel="sos",
            category="SOS"
        )

        # 2. Broadcast to specific incident channel
        await manager.broadcast_ws({
            "event": event_name,
            "channel": f"sos:{sos.id}",
            "category": "SOS",
            "timestamp": utc_now().isoformat(),
            "data": base_data
        }, channel=f"sos:{sos.id}")

        # 3. Direct notify requester
        requester_id = sos.requester_user_id or sos.user_id
        if requester_id:
            await manager.send_to_user(requester_id, {
                "event": event_name,
                "channel": f"user:{requester_id}",
                "category": "SOS",
                "timestamp": utc_now().isoformat(),
                "data": base_data
            })

        # 4. Direct notify assigned responder
        if sos.accepted_by:
            # Include authorized exact coordinates for the assigned responder
            responder_data = dict(base_data)
            responder_data["latitude"] = sos.latitude
            responder_data["longitude"] = sos.longitude
            responder_data["accuracy_meters"] = sos.accuracy_meters
            responder_data["caller_name"] = sos.caller_name
            responder_data["address"] = sos.address
            
            await manager.send_to_user(sos.accepted_by, {
                "event": event_name,
                "channel": f"user:{sos.accepted_by}",
                "category": "SOS",
                "timestamp": utc_now().isoformat(),
                "data": responder_data
            })

    @classmethod
    async def broadcast_safe_event(
        cls,
        safe_event: Any,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Broadcasts citizen SAFE declaration to general safety and SOS channels.
        """
        data = {
            "id": safe_event.id,
            "user_id": safe_event.user_id,
            "device_id": safe_event.device_id,
            "sos_id": safe_event.sos_id,
            "user_name": safe_event.user_name,
            "status": safe_event.status,
            "message": safe_event.message,
            "latitude": safe_event.latitude,
            "longitude": safe_event.longitude,
            "location_name": safe_event.location_name,
            "district": safe_event.district,
            "state": safe_event.state,
            "country": safe_event.country,
            "created_at": safe_event.created_at.isoformat() if safe_event.created_at else "",
        }
        if extra_data:
            data.update(extra_data)

        # 1. General safety & SOS broadcast
        await EventBroker.publish_event(
            event_type="SAFE_CREATED",
            data=data,
            channel="sos",
            category="SAFE"
        )
        await manager.broadcast_ws({
            "event": "SAFE_CREATED",
            "channel": "safe",
            "category": "SAFE",
            "timestamp": utc_now().isoformat(),
            "data": data
        }, channel="safe")

        # 2. If associated with an SOS, broadcast to that SOS channel
        if safe_event.sos_id:
            await manager.broadcast_ws({
                "event": "SOS_RESOLVED_BY_SAFE",
                "channel": f"sos:{safe_event.sos_id}",
                "category": "SOS",
                "timestamp": utc_now().isoformat(),
                "data": data
            }, channel=f"sos:{safe_event.sos_id}")

