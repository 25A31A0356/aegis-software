"""
AEGIS UNIFIED DATA CORE - Admin Management & Audit API
/api/v1/admin
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import AuditLog, ProcessingJob, RawObservation, User
from backend.app.schemas.common import ApiResponse
from backend.app.core.security import verify_password, create_access_token
from backend.app.api.deps import require_admin_role

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


@router.post("/auth/login", response_model=ApiResponse[LoginResponse])
async def admin_login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticates administrator and issues JWT token."""
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator email or password."
        )

    token = create_access_token(subject=user.id, role=user.role)
    return ApiResponse(
        success=True,
        data=LoginResponse(
            access_token=token,
            user={"id": user.id, "email": user.email, "role": user.role, "full_name": user.full_name}
        )
    )


@router.get("/audit-logs", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_role)
):
    """Returns immutable administrative action logs."""
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    items = [
        {
            "id": log.id,
            "user_email": log.user_email,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "client_ip": log.client_ip,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]

    return ApiResponse(success=True, data=items)


@router.get("/jobs", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_processing_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_role)
):
    """Returns history of background ingestion jobs."""
    stmt = select(ProcessingJob).order_by(desc(ProcessingJob.started_at)).limit(limit)
    res = await db.execute(stmt)
    jobs = res.scalars().all()

    items = [
        {
            "id": j.id,
            "data_source_id": j.data_source_id,
            "job_type": j.job_type,
            "status": j.status,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "duration_ms": round(j.duration_ms, 2),
            "records_ingested": j.records_ingested,
            "records_failed": j.records_failed,
            "error_message": j.error_message
        }
        for j in jobs
    ]

    return ApiResponse(success=True, data=items)


@router.get("/raw-data-explorer", response_model=ApiResponse[List[Dict[str, Any]]])
async def explore_raw_data(
    source_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_role)
):
    """
    Data Explorer: Inspects raw payloads side-by-side with normalized data for auditability.
    """
    stmt = select(RawObservation).order_by(desc(RawObservation.received_at))
    if source_id:
        stmt = stmt.where(RawObservation.data_source_id == source_id)
    stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    raws = res.scalars().all()

    items = [
        {
            "raw_id": r.id,
            "data_source_id": r.data_source_id,
            "source_record_id": r.source_record_id,
            "payload_format": r.payload_format,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "raw_payload": r.raw_payload
        }
        for r in raws
    ]

    return ApiResponse(success=True, data=items)
