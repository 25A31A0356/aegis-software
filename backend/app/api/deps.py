"""
AEGIS UNIFIED DATA CORE - API Dependencies & Security Guards
Handles DB session injection, JWT authentication, RBAC authorization, and Sliding-Window Rate Limiting.
"""
import time
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.database.session import get_db
from backend.app.database.models import User
from backend.app.core.security import decode_token
from backend.app.core.config import settings
from backend.app.cache.redis_client import CacheManager
from backend.app.utils.logger import logger

security_scheme = HTTPBearer(auto_error=False)


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


async def require_admin_role(
    user: User = Depends(require_authenticated_user)
) -> User:
    if user.role not in ("admin", "official"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to administrative and disaster response personnel."
        )
    return user


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
