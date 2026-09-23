"""
AEGIS UNIFIED DATA CORE - Push Notifications API
/api/v1/notifications
Endpoints for device push token registration, notification history,
delivery auditing, client delivery acknowledgements (ACK), and delivery state testing.
Enhanced with strict recipient authorization and production test-dispatch guards.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_, and_, func
from backend.app.database.session import get_db
from backend.app.database.models import DeviceToken, NotificationDeliveryRecord, User, utc_now
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.notifications.service import PushNotificationService
from backend.app.api.deps import rate_limit_check, get_current_user
from backend.app.core.config import settings

router = APIRouter(prefix="/notifications", tags=["Mobile Push Notifications"])


class TokenRegisterRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    push_token: str = Field(..., min_length=5, max_length=512)
    platform: Optional[str] = Field(default="ANDROID", description="ANDROID, IOS, WEB")
    provider: Optional[str] = Field(default="EXPO", description="EXPO, FCM, APNS")
    user_id: Optional[str] = Field(default=None)


class DeliveryAckRequest(BaseModel):
    device_id: Optional[str] = Field(default=None)
    device_token: Optional[str] = Field(default=None)
    client_timestamp: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class TestDispatchPayload(BaseModel):
    device_token: str = Field(...)
    notification_type: str = Field(default="CRITICAL_ALERT", description="SOS_ASSIGNMENT, SOS_STATUS, CRITICAL_ALERT, REPORT_VERIFICATION")
    title: str = Field(default="Test Emergency Alert")
    body: str = Field(default="This is a delivery verification test.")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    recipient_id: Optional[str] = Field(default="test_recipient")


class NotificationItemSchema(BaseModel):
    id: str
    notification_type: str
    recipient_type: str
    recipient_id: str
    device_token: Optional[str]
    channel: str
    title: str
    body: str
    data: Dict[str, Any]
    status: str  # PENDING, DISPATCHED, DELIVERED, REJECTED_BY_PROVIDER, FAILED, ACKNOWLEDGED
    provider_response: Dict[str, Any]
    error_reason: Optional[str]
    dispatched_at: Optional[str]
    delivered_at: Optional[str]
    acknowledged_at: Optional[str]
    created_at: str
    updated_at: str


def _map_delivery_to_schema(d: NotificationDeliveryRecord) -> NotificationItemSchema:
    return NotificationItemSchema(
        id=d.id,
        notification_type=d.notification_type,
        recipient_type=d.recipient_type,
        recipient_id=d.recipient_id,
        device_token=d.device_token,
        channel=d.channel,
        title=d.title,
        body=d.body,
        data=d.data or {},
        status=d.status,
        provider_response=d.provider_response or {},
        error_reason=d.error_reason,
        dispatched_at=d.dispatched_at.isoformat() if d.dispatched_at else None,
        delivered_at=d.delivered_at.isoformat() if d.delivered_at else None,
        acknowledged_at=d.acknowledged_at.isoformat() if d.acknowledged_at else None,
        created_at=d.created_at.isoformat() if d.created_at else "",
        updated_at=d.updated_at.isoformat() if d.updated_at else ""
    )


@router.post("/tokens/register", response_model=ApiResponse[Dict[str, Any]])
@router.post("/register-token", response_model=ApiResponse[Dict[str, Any]])
async def register_device_push_token(
    payload: TokenRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Registers or updates an active mobile push token (Expo / FCM / APNs).
    """
    user_id = (current_user.id if current_user else None) or payload.user_id or x_aegis_user_id
    token_record = await PushNotificationService.register_device_token(
        db=db,
        device_id=payload.device_id,
        push_token=payload.push_token,
        platform=payload.platform or "ANDROID",
        provider_name=payload.provider or "EXPO",
        user_id=user_id
    )

    return ApiResponse(
        success=True,
        data={
            "id": token_record.id,
            "device_id": token_record.device_id,
            "push_token": token_record.push_token,
            "platform": token_record.platform,
            "provider": token_record.provider,
            "is_active": token_record.is_active,
            "registered_at": token_record.last_registered_at.isoformat() if token_record.last_registered_at else ""
        },
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="device_registration",
            source_authority="AEGIS Mobile Push Notification Service",
            processing_version="2.0.0"
        )
    )


@router.get("", response_model=ApiResponse[List[NotificationItemSchema]])
async def list_notifications(
    user_id: Optional[str] = Query(default=None),
    device_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Fetch notification history for the authenticated user or device.
    """
    resolved_user_id = (current_user.id if current_user else None) or user_id or x_aegis_user_id

    query = select(NotificationDeliveryRecord).order_by(desc(NotificationDeliveryRecord.created_at))
    filters = []
    if resolved_user_id:
        filters.append(NotificationDeliveryRecord.recipient_id == resolved_user_id)
    if device_id:
        filters.append(NotificationDeliveryRecord.recipient_id == device_id)

    if filters:
        query = query.where(or_(*filters))

    query = query.limit(limit)
    res = await db.execute(query)
    deliveries = res.scalars().all()

    return ApiResponse(
        success=True,
        data=[_map_delivery_to_schema(d) for d in deliveries],
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="notification_history",
            source_authority="AEGIS Notification Delivery Core",
            processing_version="2.0.0"
        )
    )


@router.get("/deliveries", response_model=ApiResponse[List[NotificationItemSchema]])
async def audit_notification_deliveries(
    status: Optional[str] = Query(default=None, description="DISPATCHED, DELIVERED, REJECTED_BY_PROVIDER, FAILED, PENDING, ALL"),
    notification_type: Optional[str] = Query(default=None),
    recipient_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Operator audit endpoint for inspecting delivery states and provider rejection logs.
    """
    query = select(NotificationDeliveryRecord).order_by(desc(NotificationDeliveryRecord.created_at))

    if status and status.upper() != "ALL":
        query = query.where(NotificationDeliveryRecord.status == status.upper())

    if notification_type:
        query = query.where(NotificationDeliveryRecord.notification_type == notification_type.upper())

    if recipient_id:
        query = query.where(NotificationDeliveryRecord.recipient_id == recipient_id)

    query = query.offset(offset).limit(limit)
    res = await db.execute(query)
    deliveries = res.scalars().all()

    return ApiResponse(
        success=True,
        data=[_map_delivery_to_schema(d) for d in deliveries],
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="delivery_audit",
            source_authority="AEGIS Push Notification Delivery Auditor",
            processing_version="2.0.0"
        )
    )


@router.post("/{notification_id}/ack", response_model=ApiResponse[NotificationItemSchema])
@router.post("/{notification_id}/acknowledge", response_model=ApiResponse[NotificationItemSchema])
async def acknowledge_notification_delivery(
    notification_id: str,
    payload: Optional[DeliveryAckRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Delivery acknowledgement (ACK) from mobile / web client.
    Transitions status from DISPATCHED to DELIVERED.
    SECURED: Enforces recipient authorization preventing arbitrary users from acknowledging other users' notifications.
    """
    # 1. Fetch notification delivery record
    res = await db.execute(
        select(NotificationDeliveryRecord).where(NotificationDeliveryRecord.id == notification_id)
    )
    record = res.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Notification delivery record '{notification_id}' not found.")

    # 2. Authorization validation
    caller_user_id = (current_user.id if current_user else None) or x_aegis_user_id
    caller_device_id = payload.device_id if payload else None
    caller_device_token = payload.device_token if payload else None
    is_admin = bool(current_user and current_user.role in ("admin", "official", "operator"))

    is_authorized = False
    if record.recipient_type == "BROADCAST" or is_admin:
        is_authorized = True
    elif caller_user_id and record.recipient_id == caller_user_id:
        is_authorized = True
    elif caller_device_id and record.recipient_id == caller_device_id:
        is_authorized = True
    elif caller_device_token and record.device_token == caller_device_token:
        is_authorized = True
    elif caller_device_id and record.device_token and caller_device_id in record.device_token:
        is_authorized = True

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot acknowledge notification for another recipient."
        )

    metadata = payload.metadata if payload else {}
    if payload and payload.device_id:
        metadata["device_id"] = payload.device_id
    if payload and payload.client_timestamp:
        metadata["client_timestamp"] = payload.client_timestamp

    updated_record = await PushNotificationService.acknowledge_delivery(
        db=db,
        delivery_id=notification_id,
        metadata=metadata
    )

    return ApiResponse(
        success=True,
        data=_map_delivery_to_schema(updated_record),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="delivery_ack",
            source_authority="AEGIS Notification Delivery Core",
            processing_version="2.0.0"
        )
    )


@router.post("/test-dispatch", response_model=ApiResponse[NotificationItemSchema])
async def test_notification_dispatch(
    payload: TestDispatchPayload,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Test harness endpoint to verify push notification provider delivery and rejection states.
    SECURED: In production environment, this endpoint is restricted to authenticated operators/admins.
    """
    is_prod = str(settings.ENVIRONMENT).lower() == "production"
    if is_prod:
        if not current_user or current_user.role not in ("admin", "official", "operator"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Test dispatch endpoint is restricted to operators in production mode."
            )

    deliv = await PushNotificationService._send_single_notification(
        db=db,
        notification_type=payload.notification_type,
        recipient_type="TEST",
        recipient_id=payload.recipient_id or "test_recipient",
        title=payload.title,
        body=payload.body,
        data=payload.data or {},
        device_token=payload.device_token,
        channel="PUSH"
    )

    return ApiResponse(
        success=True,
        data=_map_delivery_to_schema(deliv),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="test_dispatch",
            source_authority="AEGIS Notification Test Harness",
            processing_version="2.0.0"
        )
    )
