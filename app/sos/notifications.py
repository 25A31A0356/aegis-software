"""
AEGIS UNIFIED DATA CORE - SOS Notification Delivery Subsystem
Abstracts dispatching across In-App WebSockets, Family Emergency Contacts (SMS/Alerts),
and Mobile Push Notification interfaces (FCM / APNs ready).
"""
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.models import SOSSignal, SOSNotification, utc_now
from backend.app.realtime.manager import EventBroker, manager, EVENT_SCHEMA_VERSION
from backend.app.notifications.service import PushNotificationService
from backend.app.utils.logger import logger


class BasePushAdapter:
    """Pluggable push notification adapter interface."""
    async def send_push(self, device_token: str, title: str, body: str, data: Dict[str, Any]) -> bool:
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
                "approximate_distance_km": round(dist_km, 2),
                "district": sos.district or sos.city or "Your Jurisdiction",
                "expires_at": (utc_now().timestamp() + 45),
                "offer_type": "EMERGENCY_DISPATCH_PROXIMITY"
            }

            # 1. Direct Web/App WebSocket notification
            await manager.send_to_user(
                user_id=user_id,
                message={
                    "id": f"evt_{uuid.uuid4().hex}",
                    "version": EVENT_SCHEMA_VERSION,
                    "event": "SOS_OFFER_RECEIVED",
                    "category": "SOS",
                    "channel": f"user:{user_id}",
                    "timestamp": utc_now().isoformat(),
                    "data": offer_payload
                }
            )

            # 2. Unified Push Notification Service Dispatch
            await PushNotificationService.dispatch_sos_assignment(
                db=db,
                sos=sos,
                candidate_responder_id=user_id,
                distance_km=dist_km
            )

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
        - General public/operators: Sanitized general event on channel 'sos'
        - Channel `sos:{sos_id}`: Incident channel for assigned participants
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
        await EventBroker.publish_event(
            event_type=event_name,
            data=base_data,
            channel=f"sos:{sos.id}",
            category="SOS"
        )

        # 3. Direct notify requester
        requester_id = sos.requester_user_id or sos.user_id
        if requester_id:
            await manager.send_to_user(requester_id, {
                "id": f"evt_{uuid.uuid4().hex}",
                "version": EVENT_SCHEMA_VERSION,
                "event": event_name,
                "channel": f"user:{requester_id}",
                "category": "SOS",
                "timestamp": utc_now().isoformat(),
                "data": base_data
            })

        # 4. Direct notify assigned responder
        if sos.accepted_by:
            responder_data = dict(base_data)
            responder_data["latitude"] = sos.latitude
            responder_data["longitude"] = sos.longitude
            responder_data["accuracy_meters"] = sos.accuracy_meters
            responder_data["caller_name"] = sos.caller_name
            responder_data["address"] = sos.address
            
            await manager.send_to_user(sos.accepted_by, {
                "id": f"evt_{uuid.uuid4().hex}",
                "version": EVENT_SCHEMA_VERSION,
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
        Broadcasts SAFE status event to community map and subscribers.
        """
        payload = {
            "id": safe_event.id,
            "user_id": safe_event.user_id,
            "user_name": safe_event.user_name,
            "status": "SAFE",
            "message": safe_event.message,
            "latitude": safe_event.latitude,
            "longitude": safe_event.longitude,
            "district": safe_event.district,
            "state": safe_event.state,
            "location_name": safe_event.location_name,
            "recorded_at": safe_event.recorded_at.isoformat() if safe_event.recorded_at else utc_now().isoformat()
        }
        if extra_data:
            payload.update(extra_data)

        await EventBroker.publish_event(
            event_type="SAFE_DECLARED",
            data=payload,
            channel="all",
            category="SAFE_EVENT"
        )
