"""
AEGIS UNIFIED DATA CORE - API Dependencies & Security Guards
Handles DB session injection, JWT authentication, RBAC authorization, Client Context, and Sliding-Window Rate Limiting.
"""
import time
from enum import Enum
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Security, Request, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database.session import get_db
from backend.app.database.models import User
from backend.app.core.security import decode_token
from backend.app.core.config import settings
from backend.app.cache.redis_client import CacheManager

security_scheme = HTTPBearer(auto_error=False)


class ClientType(str, Enum):
    WEB = "web"
    APP = "app"
    ADMIN = "admin"
    INTERNAL_SERVICE = "internal"


class ClientContext(BaseModel):
    client_type: ClientType
    user: Optional[Dict[str, Any]] = None if False else None
    client_ip: str
    is_admin: bool = False


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Extracts and verifies JWT token from Authorization header."""
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalars().first()
    return user


async def require_authenticated_user(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


get_current_active_user = require_authenticated_user


async def require_citizen_or_above(
    user: User = Depends(require_authenticated_user)
) -> User:
    return user


async def require_responder_or_above(
    user: User = Depends(require_authenticated_user)
) -> User:
    allowed_roles = ("responder", "sdrf_officer", "ndrf_officer", "operator", "official", "admin")
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to emergency responders and operational personnel."
        )
    return user


async def require_operator_or_above(
    user: User = Depends(require_authenticated_user)
) -> User:
    allowed_roles = ("operator", "official", "admin")
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to command center operators and disaster officials."
        )
    return user


async def require_official_or_above(
    user: User = Depends(require_authenticated_user)
) -> User:
    allowed_roles = ("official", "admin")
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to authorized disaster management officials."
        )
    return user


async def require_admin_role(
    user: User = Depends(require_authenticated_user)
) -> User:
    if user.role not in ("admin", "official"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to administrative personnel."
        )
    return user


async def get_client_context(
    request: Request,
    x_aegis_client: Optional[str] = Header(default=None, alias="X-Aegis-Client"),
    user: Optional[User] = Depends(get_current_user)
) -> ClientContext:
    """
    Extracts caller client context distinguishing WEB, APP, ADMIN, and INTERNAL_SERVICE.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    # If authenticated admin user
    if user and user.role in ("admin", "official"):
        return ClientContext(
            client_type=ClientType.ADMIN,
            client_ip=client_ip,
            is_admin=True
        )

    # Check client header
    c_type = ClientType.WEB
    if x_aegis_client:
        clean_c = x_aegis_client.strip().lower()
        if clean_c == "app":
            c_type = ClientType.APP
        elif clean_c == "internal":
            c_type = ClientType.INTERNAL_SERVICE
        elif clean_c == "admin" and user and user.role in ("admin", "official"):
            c_type = ClientType.ADMIN

    return ClientContext(
        client_type=c_type,
        client_ip=client_ip,
        is_admin=False
    )


async def rate_limit_check(request: Request):
    """Sliding-window IP rate limiting guard."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    key = f"rate_limit_{client_ip}"
    current_time = int(time.time())

    # Get cached request timestamps
    history = await CacheManager.get(key) or []
    # Retain only timestamps from the last 60 seconds
    valid_history = [ts for ts in history if current_time - ts < 60]

    if len(valid_history) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please throttle your emergency intelligence queries."
        )

    valid_history.append(current_time)
    await CacheManager.set(key, valid_history, ttl_seconds=65)
