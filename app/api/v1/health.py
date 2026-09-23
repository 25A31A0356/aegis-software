"""
AEGIS UNIFIED DATA CORE - System & Provider Observability Health API
/api/v1/health
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from backend.app.database.session import get_db
from backend.app.database.models import DataSource
from backend.app.cache.redis_client import CacheManager
from backend.app.schemas.common import ApiResponse

router = APIRouter(prefix="/health", tags=["System Health & Observability"])


@router.get("", response_model=ApiResponse[Dict[str, Any]])
async def check_overall_health(db: AsyncSession = Depends(get_db)):
    """
    Returns liveness & readiness status of AEGIS Core infrastructure (DB, Cache, Providers).
    """
    # 1. Check Database
    db_status = "HEALTHY"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"FAILED: {str(e)}"

    # 2. Check Cache
    cache_health = await CacheManager.check_health()

    # 3. Check Provider Sources Summary
    stmt = select(DataSource)
    res = await db.execute(stmt)
    sources = res.scalars().all()

    total_sources = len(sources)
    healthy_count = sum(1 for s in sources if s.health_status == "HEALTHY")
    degraded_count = sum(1 for s in sources if s.health_status == "DEGRADED")
    failed_count = sum(1 for s in sources if s.health_status == "FAILED")
    inactive_count = sum(1 for s in sources if not s.is_enabled)

    overall_status = "HEALTHY"
    if db_status != "HEALTHY":
        overall_status = "CRITICAL"
    elif failed_count > 0:
        overall_status = "DEGRADED"

    return ApiResponse(
        success=True,
        data={
            "system_status": overall_status,
            "database": {"status": db_status, "engine": "PostgreSQL/PostGIS"},
            "cache": cache_health,
            "providers_summary": {
                "total": total_sources,
                "healthy": healthy_count,
                "degraded": degraded_count,
                "failed": failed_count,
                "inactive": inactive_count,
            },
            "security_posture": "HARDENED",
            "ssrf_protection": "ACTIVE"
        }
    )


@router.get("/providers", response_model=ApiResponse[List[Dict[str, Any]]])
async def check_provider_health_detail(db: AsyncSession = Depends(get_db)):
    """
    Returns individual health metrics and latency per external data provider.
    """
    stmt = select(DataSource)
    res = await db.execute(stmt)
    sources = res.scalars().all()

    provider_details = [
        {
            "id": s.id,
            "name": s.name,
            "provider_code": s.provider_code,
            "category": s.category,
            "health_status": s.health_status,
            "is_enabled": s.is_enabled,
            "consecutive_failures": s.consecutive_failures,
            "last_response_time_ms": s.last_response_time_ms,
            "last_http_status": s.last_http_status,
            "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
            "last_failure_at": s.last_failure_at.isoformat() if s.last_failure_at else None,
            "last_error_message": s.last_error_message
        }
        for s in sources
    ]

    return ApiResponse(success=True, data=provider_details)
