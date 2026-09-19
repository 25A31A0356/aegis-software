"""
AEGIS CENTRAL DATA GATEWAY - Application & User Authentication API
/api/v1/auth
Handles user registration, user login, client key verification, and JWT issuance for Web & App.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database.session import get_db
from backend.app.database.models import User
from backend.app.schemas.common import ApiResponse
from backend.app.core.security import verify_password, get_password_hash, create_access_token
from backend.app.core.config import settings
from backend.app.api.deps import require_authenticated_user

router = APIRouter(prefix="/auth", tags=["Application & User Authentication"])


class RegisterUserRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6)
    full_name: str
    role: Optional[str] = "citizen"  # citizen, responder, volunteer


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class ClientVerifyRequest(BaseModel):
    client_type: str  # web, app
    client_key: Optional[str] = None


class ClientVerifyResponse(BaseModel):
    valid: bool
    client_type: str
    access_tier: str
    rate_limit_per_minute: int
    message: str


@router.post("/register", response_model=ApiResponse[AuthTokenResponse])
async def register_user(
    payload: RegisterUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """Registers a new user account (for Web or Mobile App)."""
    # Check if email exists
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email address already exists."
        )

    # Safe role assignment (admin role must be granted directly by existing admin)
    assigned_role = "citizen"
    if payload.role in ("citizen", "responder", "volunteer"):
        assigned_role = payload.role

    new_user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=assigned_role,
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(subject=new_user.id, role=new_user.role)
    return ApiResponse(
        success=True,
        data=AuthTokenResponse(
            access_token=token,
            user={
                "id": new_user.id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role
            }
        )
    )


@router.post("/login", response_model=ApiResponse[AuthTokenResponse])
async def user_login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticates user and returns JWT access token."""
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated."
        )

    token = create_access_token(subject=user.id, role=user.role)
    return ApiResponse(
        success=True,
        data=AuthTokenResponse(
            access_token=token,
            user={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role
            }
        )
    )


@router.get("/me", response_model=ApiResponse[Dict[str, Any]])
async def get_current_user_profile(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns profile and synchronized preferences for currently authenticated user."""
    from backend.app.database.models import UserPreference
    pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
    pref = pref_res.scalars().first()

    return ApiResponse(
        success=True,
        data={
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "saved_locations": pref.saved_locations if pref else [],
            "hazard_subscriptions": pref.hazard_subscriptions if pref else ["FLOOD", "EARTHQUAKE", "CYCLONE", "FIRE"],
            "push_enabled": pref.push_enabled if pref else True,
            "sms_alerts_enabled": pref.sms_alerts_enabled if pref else False,
            "language": pref.language if pref else "en",
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        }
    )


class UpdatePreferencesRequest(BaseModel):
    saved_locations: Optional[list] = None
    hazard_subscriptions: Optional[list] = None
    push_enabled: Optional[bool] = None
    sms_alerts_enabled: Optional[bool] = None
    language: Optional[str] = None


@router.put("/preferences", response_model=ApiResponse[Dict[str, Any]])
async def update_user_preferences(
    payload: UpdatePreferencesRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """Updates user saved locations, hazard alerts, and notification preferences."""
    from backend.app.database.models import UserPreference
    pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
    pref = pref_res.scalars().first()

    if not pref:
        pref = UserPreference(
            user_id=current_user.id,
            saved_locations=payload.saved_locations or [],
            hazard_subscriptions=payload.hazard_subscriptions or ["FLOOD", "EARTHQUAKE", "CYCLONE", "FIRE"],
            push_enabled=payload.push_enabled if payload.push_enabled is not None else True,
            sms_alerts_enabled=payload.sms_alerts_enabled if payload.sms_alerts_enabled is not None else False,
            language=payload.language or "en"
        )
        db.add(pref)
    else:
        if payload.saved_locations is not None:
            pref.saved_locations = payload.saved_locations
        if payload.hazard_subscriptions is not None:
            pref.hazard_subscriptions = payload.hazard_subscriptions
        if payload.push_enabled is not None:
            pref.push_enabled = payload.push_enabled
        if payload.sms_alerts_enabled is not None:
            pref.sms_alerts_enabled = payload.sms_alerts_enabled
        if payload.language is not None:
            pref.language = payload.language

    await db.commit()
    await db.refresh(pref)

    return ApiResponse(
        success=True,
        data={
            "saved_locations": pref.saved_locations,
            "hazard_subscriptions": pref.hazard_subscriptions,
            "push_enabled": pref.push_enabled,
            "sms_alerts_enabled": pref.sms_alerts_enabled,
            "language": pref.language
        }
    )


@router.post("/client-verify", response_model=ApiResponse[ClientVerifyResponse])
async def verify_client_credentials(
    payload: ClientVerifyRequest,
    x_aegis_client: Optional[str] = Header(default=None, alias="X-Aegis-Client"),
    x_aegis_client_key: Optional[str] = Header(default=None, alias="X-Aegis-Client-Key")
):
    """
    Verifies Web or Mobile application client keys and returns access parameters.
    Allows clients to validate their gateway configuration before making telemetry queries.
    """
    c_type = (payload.client_type or x_aegis_client or "web").lower()
    c_key = payload.client_key or x_aegis_client_key

    is_valid = False
    if c_type == "web":
        if not settings.AEGIS_WEB_CLIENT_KEY or c_key == settings.AEGIS_WEB_CLIENT_KEY:
            is_valid = True
    elif c_type == "app":
        if not settings.AEGIS_APP_CLIENT_KEY or c_key == settings.AEGIS_APP_CLIENT_KEY:
            is_valid = True

    return ApiResponse(
        success=True,
        data=ClientVerifyResponse(
            valid=is_valid,
            client_type=c_type,
            access_tier="STANDARD_GATEWAY_ACCESS" if is_valid else "UNAUTHORIZED_CLIENT",
            rate_limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            message="Client verified successfully for AEGIS Central Gateway." if is_valid else "Invalid client application credentials."
        )
    )
