"""
AEGIS UNIFIED DATA CORE - AI/ML Disaster Intelligence & Context Synthesis API
/api/v1/ai
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Query, Body
from pydantic import BaseModel
from backend.app.schemas.common import ApiResponse, ProvenanceMetadata
from backend.app.engines.ai_layer import AIIntelligenceLayer
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/ai", tags=["AI Context Synthesis"])


class AIChatRequest(BaseModel):
    message: str
    location_name: str = "Regional Sector"
    context_hazards: List[Dict[str, Any]] = []


@router.post("/synthesize", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def synthesize_emergency_overview(
    payload: AIChatRequest
):
    """
    Synthesizes contextual disaster situational overview from validated observations.
    Carries explicit 'data_type=ai_analysis' provenance.
    """
    # 1. Base telemetry situation report
    synth = AIIntelligenceLayer.synthesize_situation_report(
        location_name=payload.location_name,
        active_hazards=payload.context_hazards,
        risk_score=65.0 if payload.context_hazards else 15.0,
        risk_level="HIGH" if payload.context_hazards else "LOW"
    )

    # 2. Check for dynamic Gemini advisory if user supplied query and key
    if payload.message:
        gemini_advice = await AIIntelligenceLayer.generate_gemini_advisory(payload.message, payload.location_name)
        if gemini_advice:
            synth["ai_generated_advisory"] = gemini_advice
            synth["provenance"]["model"] = "gemini-1.5-flash"

    return ApiResponse(
        success=True,
        data=synth,
        provenance=ProvenanceMetadata(
            data_type="ai_analysis",
            source_authority="AEGIS AI Intelligence & Decision Support Layer",
            processing_version="1.0.0"
        )
    )
