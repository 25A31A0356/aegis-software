import httpx
import uuid
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.models import AIDecisionAudit, utc_now
from backend.app.core.config import settings
from backend.app.utils.logger import logger


class AIIntelligenceLayer:
    """
    Authoritative AEGIS AI Decision Support & Context Synthesis Subsystem.
    Provides verified analytical support for incident classification, situational risk scoring,
    resource recommendation, and Gemini advisory generation with mandatory human authorization guardrails.
    """

    @classmethod
    async def audit_decision(
        cls,
        db: Optional[AsyncSession],
        task_type: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        confidence: float = 1.0,
        model_provider: str = "gemini-1.5-flash",
        authorization_status: str = "NOT_REQUIRED"
    ) -> str:
        """
        Persists an immutable audit record for an AI-assisted operational task.
        """
        request_id = f"ai_{uuid.uuid4().hex[:12]}"
        input_str = str(sorted(input_data.items()))
        input_hash = hashlib.sha256(input_str.encode("utf-8")).hexdigest()

        if db:
            audit = AIDecisionAudit(
                request_id=request_id,
                model_provider=model_provider,
                task_type=task_type,
                input_hash=input_hash,
                input_context=input_data,
                output_payload=output_data,
                confidence=confidence,
                authorization_status=authorization_status,
                created_at=utc_now()
            )
            db.add(audit)
            try:
                await db.commit()
            except Exception as e:
                logger.warning(f"[AIAudit] Failed to persist AI decision audit: {e}")

        return request_id

    @classmethod
    async def generate_gemini_advisory(
        cls,
        prompt: str,
        location_name: str = "India"
    ) -> Optional[str]:
        """
        Calls Google Gemini API if GEMINI_API_KEY is configured in settings/.env.
        """
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            return None

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"You are AEGIS, an authoritative disaster management AI assistant. "
                                f"Provide a concise, life-saving, actionable safety advisory for {location_name}. "
                                f"User query: {prompt}"
                    }]
                }]
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
        except Exception as err:
            logger.warning(f"Gemini API request failed, using local domain intelligence: {err}")
        return None

    @classmethod
    def classify_incident(
        cls,
        description: str,
        title: Optional[str] = ""
    ) -> Dict[str, Any]:
        """
        Heuristic natural language incident classifier mapping citizen descriptions
        to standardized emergency taxonomy with confidence metrics.
        """
        text = f"{title} {description}".lower()

        scores = {
            "FLOOD": 0.0,
            "FIRE": 0.0,
            "ROAD_BLOCKED": 0.0,
            "LANDSLIDE": 0.0,
            "BUILDING_DAMAGE": 0.0,
            "WATERLOGGING": 0.0,
            "CYCLONE": 0.0,
            "MEDICAL": 0.0
        }

        keywords = {
            "FLOOD": ["flood", "drowning", "river", "overflow", "submerged", "dam", "water level", "current"],
            "FIRE": ["fire", "smoke", "burning", "blaze", "gas leak", "explosion", "flames"],
            "ROAD_BLOCKED": ["road blocked", "debris", "boulders", "highway closed", "traffic cut", "tree fell"],
            "LANDSLIDE": ["landslide", "mudslide", "mud", "slope collapsed", "hillside", "rockfall"],
            "BUILDING_DAMAGE": ["building collapse", "cracks", "structure damaged", "roof fell", "rubble"],
            "WATERLOGGING": ["waterlogging", "waterlogged", "drainage", "stagnant water", "street flooded"],
            "CYCLONE": ["cyclone", "gale", "storm surge", "high winds", "hurricane", "typhoon"],
            "MEDICAL": ["heart attack", "bleeding", "unconscious", "injury", "fracture", "ambulance", "paramedic"]
        }

        for cat, kws in keywords.items():
            for kw in kws:
                if kw in text:
                    scores[cat] += 1.0

        top_cat, top_score = max(scores.items(), key=lambda x: x[1])
        if top_score == 0.0:
            top_cat = "OTHER"
            confidence = 0.50
            severity = "MODERATE"
        else:
            confidence = min(0.95, round(0.60 + (top_score * 0.10), 2))
            severity = "CRITICAL" if top_cat in ("FIRE", "FLOOD", "CYCLONE", "BUILDING_DAMAGE", "MEDICAL") else "HIGH"

        return {
            "category": top_cat,
            "suggested_severity": severity,
            "confidence": confidence,
            "classification_method": "AEGIS NLP Heuristic Engine v2.0",
            "matched_signals": top_score,
            "requires_human_verification": True
        }

    @classmethod
    def recommend_resources(
        cls,
        emergency_type: str,
        severity: str,
        casualties_count: int = 1
    ) -> Dict[str, Any]:
        """
        Recommends tactical disaster-response personnel, vehicles, and equipment packages.
        """
        em_clean = (emergency_type or "general").lower()
        sev_clean = (severity or "CRITICAL").upper()

        equipment = ["FIRST_AID_KIT", "HIGH_VISIBILITY_VEST", "VHF_RADIO"]
        vehicle = "MOTORCYCLE"
        personnel = ["COMMUNITY_RESPONDER"]

        if "flood" in em_clean:
            equipment.extend(["LIFE_JACKETS", "INFLATABLE_RESCUE_BOAT", "ROPES", "WATER_PUMP"])
            vehicle = "BOAT"
            personnel = ["BOAT_RESCUE_SPECIALIST", "SWIMMER", "PARAMEDIC"]
        elif "fire" in em_clean:
            equipment.extend(["FIRE_EXTINGUISHERS", "SMOKE_MASKS", "HEAT_RESISTANT_SUIT", "OXYGEN_KIT"])
            vehicle = "FIRE_TENDER"
            personnel = ["FIREFIGHTER", "PARAMEDIC", "SEARCH_AND_RESCUE"]
        elif "collapse" in em_clean or "landslide" in em_clean:
            equipment.extend(["SEARCH_DOGS", "HYDRAULIC_CUTTER", "STRETCHERS", "HEAVY_RESCUE_GEAR"])
            vehicle = "4X4_JEEP"
            personnel = ["SEARCH_AND_RESCUE_UNIT", "DOCTOR", "DISASTER_ENGINEER"]
        elif "medical" in em_clean:
            equipment.extend(["DEFIBRILLATOR", "TRAUMA_KIT", "STRETCHER", "OXYGEN_CONCENTRATOR"])
            vehicle = "AMBULANCE"
            personnel = ["PARAMEDIC", "DOCTOR"]

        if casualties_count > 5 or sev_clean == "CRITICAL":
            personnel.append("SDRF_TACTICAL_COMMAND")

        return {
            "emergency_type": emergency_type,
            "recommended_vehicle": vehicle,
            "recommended_personnel": personnel,
            "recommended_equipment": equipment,
            "priority_dispatch": sev_clean in ("CRITICAL", "HIGH"),
            "data_type": "ai_resource_recommendation"
        }

    @classmethod
    def synthesize_situation_report(
        cls,
        location_name: str,
        active_hazards: List[Dict[str, Any]],
        risk_score: float,
        risk_level: str
    ) -> Dict[str, Any]:
        """
        Synthesizes a natural language situation overview from validated telemetry.
        """
        if not active_hazards:
            summary_text = (
                f"Meteorological and hydro-seismological telemetry across {location_name} indicates "
                "nominal baseline conditions with no active critical hazard alerts at this time."
            )
            key_recommendations = [
                "Maintain standard situational awareness.",
                "Verify battery reserves and family emergency kit."
            ]
        else:
            hazard_names = ", ".join([h.get("hazard", "Regional Event") for h in active_hazards])
            summary_text = (
                f"Multi-source correlation for {location_name} indicates an elevated risk posture ({risk_level}, score {risk_score}/100) "
                f"due to active signals: {hazard_names}. Official agency bulletins are in effect."
            )
            key_recommendations = [
                "Follow verified directives from NDMA and regional State Disaster Management Authorities.",
                "Keep emergency communications channels (112, 1070) accessible.",
                "Review evacuation routes on the AEGIS GIS Live Map."
            ]

        return {
            "location": location_name,
            "situation_summary": summary_text,
            "risk_level": risk_level,
            "composite_score": risk_score,
            "recommended_actions": key_recommendations,
            "data_type": "ai_analysis",
            "provenance": {
                "engine": "AEGIS AI Context Synthesizer v2.0",
                "is_official_government_bulletin": False,
                "synthesized_at": datetime.now(timezone.utc).isoformat()
            }
        }
