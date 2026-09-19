import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.core.config import settings
from backend.app.utils.logger import logger


class AIIntelligenceLayer:
    @classmethod
    async def generate_gemini_advisory(
        cls,
        prompt: str,
        location_name: str = "India"
    ) -> Optional[str]:
        """
        Calls Google Gemini API if GEMINI_API_KEY is configured in settings/.env
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
            logger.warn(f"Gemini API request failed, using local domain intelligence: {err}")
        return None

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
                "engine": "AEGIS AI Context Synthesizer v1.0",
                "is_official_government_bulletin": False,
                "synthesized_at": datetime.now(timezone.utc).isoformat()
            }
        }
