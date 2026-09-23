"""
AEGIS UNIFIED DATA CORE - AI/ML Disaster Intelligence & Context Synthesis API
/api/v1/ai
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.schemas.common import ApiResponse, ProvenanceMetadata
from backend.app.engines.ai_layer import AIIntelligenceLayer
from backend.app.database.session import get_db
from backend.app.database.models import AIDecisionAudit, User, utc_now
from backend.app.api.deps import (
    get_current_active_user,
    require_operator_or_above,
    require_official_or_above,
    rate_limit_check
)

router = APIRouter(prefix="/ai", tags=["AI Context Synthesis & Decision Support"])


class AIChatRequest(BaseModel):
    message: str
    location_name: str = "Regional Sector"
    context_hazards: List[Dict[str, Any]] = []


class IncidentClassifyRequest(BaseModel):
    title: Optional[str] = ""
    description: str = Field(..., min_length=3, description="Citizen incident description or report text")


class RiskAssessRequest(BaseModel):
    location_name: str
    hazard_type: str
    severity: str
    affected_population_estimate: Optional[int] = 100


class ResourceRecommendRequest(BaseModel):
    emergency_type: str
    severity: str
    casualties_count: Optional[int] = 1


class DecisionAuthorizeRequest(BaseModel):
    authorization_status: str = Field(..., description="AUTHORIZED, REJECTED, or OVERRIDDEN")
    operator_notes: Optional[str] = ""


@router.post("/synthesize", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def synthesize_emergency_overview(
    payload: AIChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Synthesizes contextual disaster situational overview from validated observations.
    Carries explicit 'data_type=ai_analysis' provenance.
    """
    synth = AIIntelligenceLayer.synthesize_situation_report(
        location_name=payload.location_name,
        active_hazards=payload.context_hazards,
        risk_score=65.0 if payload.context_hazards else 15.0,
        risk_level="HIGH" if payload.context_hazards else "LOW"
    )

    if payload.message:
        gemini_advice = await AIIntelligenceLayer.generate_gemini_advisory(payload.message, payload.location_name)
        if gemini_advice:
            synth["ai_generated_advisory"] = gemini_advice
            synth["provenance"]["model"] = "gemini-1.5-flash"

    # Audit the synthesis action
    audit_id = await AIIntelligenceLayer.audit_decision(
        db=db,
        task_type="SITUATION_SYNTHESIS",
        input_data={"location": payload.location_name, "message": payload.message, "hazards_count": len(payload.context_hazards)},
        output_data={"summary": synth.get("situation_summary", ""), "risk_level": synth.get("risk_level", "")},
        confidence=0.85,
        authorization_status="NOT_REQUIRED"
    )
    synth["audit_request_id"] = audit_id

    return ApiResponse(
        success=True,
        data=synth,
        provenance=ProvenanceMetadata(
            data_type="ai_analysis",
            source_authority="AEGIS AI Intelligence & Decision Support Layer",
            processing_version="2.0.0"
        )
    )


@router.post("/classify-incident", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def classify_incident(
    payload: IncidentClassifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Classifies raw incident descriptions into standardized disaster taxonomies with confidence scoring.
    """
    result = AIIntelligenceLayer.classify_incident(
        description=payload.description,
        title=payload.title
    )

    audit_id = await AIIntelligenceLayer.audit_decision(
        db=db,
        task_type="INCIDENT_CLASSIFICATION",
        input_data={"title": payload.title, "description": payload.description},
        output_data=result,
        confidence=result.get("confidence", 0.70),
        authorization_status="PENDING" if result.get("requires_human_verification") else "NOT_REQUIRED"
    )
    result["audit_request_id"] = audit_id

    return ApiResponse(
        success=True,
        data=result,
        provenance=ProvenanceMetadata(
            data_type="ai_classification",
            source_authority="AEGIS NLP Heuristic Engine v2.0",
            processing_version="2.0.0"
        )
    )


@router.post("/recommend-resources", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def recommend_resources(
    payload: ResourceRecommendRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Recommends response units, tactical equipment, and vehicles based on incident severity.
    """
    result = AIIntelligenceLayer.recommend_resources(
        emergency_type=payload.emergency_type,
        severity=payload.severity,
        casualties_count=payload.casualties_count or 1
    )

    audit_id = await AIIntelligenceLayer.audit_decision(
        db=db,
        task_type="RESOURCE_RECOMMENDATION",
        input_data={"emergency_type": payload.emergency_type, "severity": payload.severity, "casualties": payload.casualties_count},
        output_data=result,
        confidence=0.90,
        authorization_status="PENDING_DISPATCH_AUTHORIZATION"
    )
    result["audit_request_id"] = audit_id

    return ApiResponse(
        success=True,
        data=result,
        provenance=ProvenanceMetadata(
            data_type="ai_resource_recommendation",
            source_authority="AEGIS Tactical Dispatch Recommender v2.0",
            processing_version="2.0.0"
        )
    )


@router.post("/assess-risk", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def assess_risk(
    payload: RiskAssessRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Computes an authoritative risk assessment index for localized emergencies.
    """
    sev_mult = {"CRITICAL": 1.0, "HIGH": 0.75, "MODERATE": 0.5, "LOW": 0.25}.get(payload.severity.upper(), 0.5)
    pop = payload.affected_population_estimate or 100
    pop_factor = min(1.0, pop / 1000.0)
    score = round(min(100.0, (sev_mult * 70.0) + (pop_factor * 30.0)), 1)

    level = "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MODERATE" if score >= 35 else "LOW"

    result = {
        "location": payload.location_name,
        "hazard_type": payload.hazard_type,
        "composite_risk_score": score,
        "risk_level": level,
        "urgency": "IMMEDIATE" if score >= 75 else "STANDARD",
        "affected_population_estimate": pop
    }

    audit_id = await AIIntelligenceLayer.audit_decision(
        db=db,
        task_type="RISK_ASSESSMENT",
        input_data=payload.dict(),
        output_data=result,
        confidence=0.88,
        authorization_status="NOT_REQUIRED"
    )
    result["audit_request_id"] = audit_id

    return ApiResponse(
        success=True,
        data=result,
        provenance=ProvenanceMetadata(
            data_type="ai_risk_assessment",
            source_authority="AEGIS Risk Matrix Evaluator v2.0",
            processing_version="2.0.0"
        )
    )


@router.get("/audit", response_model=ApiResponse[List[Dict[str, Any]]])
async def list_ai_decision_audits(
    limit: int = Query(50, ge=1, le=200),
    task_type: Optional[str] = None,
    current_user: User = Depends(require_operator_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Operator/Official endpoint to inspect immutable AI decision logs and human oversight compliance.
    """
    query = select(AIDecisionAudit).order_by(desc(AIDecisionAudit.created_at)).limit(limit)
    if task_type:
        query = query.where(AIDecisionAudit.task_type == task_type)

    res = await db.execute(query)
    audits = res.scalars().all()

    audit_list = [
        {
            "id": a.id,
            "request_id": a.request_id,
            "model_provider": a.model_provider,
            "task_type": a.task_type,
            "input_hash": a.input_hash,
            "input_context": a.input_context,
            "output_payload": a.output_payload,
            "confidence": a.confidence,
            "authorization_status": a.authorization_status,
            "authorized_by": a.authorized_by_user_id,
            "authorized_at": a.authorized_at.isoformat() if a.authorized_at else None,
            "notes": a.authorization_notes,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in audits
    ]

    return ApiResponse(
        success=True,
        data=audit_list,
        provenance=ProvenanceMetadata(
            data_type="ai_audit_trail",
            source_authority="AEGIS Governance & Human Oversight Subsystem",
            processing_version="2.0.0"
        )
    )


@router.post("/audit/{request_id}/authorize", response_model=ApiResponse[Dict[str, Any]])
async def authorize_ai_decision(
    request_id: str,
    payload: DecisionAuthorizeRequest,
    current_user: User = Depends(require_official_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Official/Admin workflow to grant human authorization or override on an AI-generated advisory or dispatch recommendation.
    """
    query = select(AIDecisionAudit).where(AIDecisionAudit.request_id == request_id)
    res = await db.execute(query)
    audit = res.scalar_one_or_none()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI decision audit record '{request_id}' not found."
        )

    valid_statuses = {"AUTHORIZED", "REJECTED", "OVERRIDDEN"}
    if payload.authorization_status.upper() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authorization status. Must be one of {valid_statuses}."
        )

    audit.authorization_status = payload.authorization_status.upper()
    audit.authorized_by_user_id = current_user.id
    audit.authorized_at = utc_now()
    if payload.operator_notes:
        audit.authorization_notes = payload.operator_notes

    await db.commit()
    await db.refresh(audit)

    return ApiResponse(
        success=True,
        data={
            "request_id": audit.request_id,
            "authorization_status": audit.authorization_status,
            "authorized_by": audit.authorized_by_user_id,
            "authorized_at": audit.authorized_at.isoformat() if audit.authorized_at else None,
            "notes": audit.authorization_notes
        },
        provenance=ProvenanceMetadata(
            data_type="human_authorization_audit",
            source_authority="AEGIS Safety & Authorization Guardrail",
            processing_version="2.0.0"
        )
    )
