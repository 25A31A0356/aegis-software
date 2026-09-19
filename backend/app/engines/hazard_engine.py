"""
AEGIS UNIFIED DATA CORE - Hazard & Risk Assessment Engine
Rules-based and statistical evaluation engine for multi-hazard alert triggering and risk categorisation.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.schemas.unified import UnifiedObservation, AlertItemSchema


class HazardEngine:
    @staticmethod
    def evaluate_observation_risk(obs: UnifiedObservation) -> Dict[str, Any]:
        """Calculates risk tier and alert eligibility for an individual observation."""
        ht = obs.hazard_type.upper()
        m = obs.measurements

        risk_tier = "LOW"
        should_trigger_alert = False
        headline = ""
        action_advisory = ""

        if ht == "WEATHER":
            precip = float(m.get("precipitation_mm", 0.0))
            wind = float(m.get("wind_speed_kmh", 0.0))
            temp = float(m.get("temperature_c", 25.0))
            if precip >= 50.0 or wind >= 80.0:
                risk_tier = "EXTREME"
                should_trigger_alert = True
                headline = "Severe Storm & Torrential Precipitation Warning"
                action_advisory = "Stay indoors. Avoid waterlogged transit corridors and power lines."
            elif precip >= 25.0 or wind >= 50.0:
                risk_tier = "HIGH"
                should_trigger_alert = True
                headline = "Heavy Precipitation & Gusty Gale Alert"
                action_advisory = "Drive with extreme caution and clear drainage channels."
            elif temp >= 42.0:
                risk_tier = "HIGH"
                should_trigger_alert = True
                headline = "Severe Heatwave Warning"
                action_advisory = "Stay hydrated and avoid direct sunlight exposure between 12:00-16:00."

        elif ht == "FLOOD":
            water_level = float(m.get("water_level_m", 0.0))
            danger_level = float(m.get("danger_level_m", 1.0))
            if danger_level > 0 and water_level >= danger_level:
                risk_tier = "EXTREME"
                should_trigger_alert = True
                headline = f"Red Alert: River Level Exceeding Critical Danger Mark ({water_level}m)"
                action_advisory = "Execute immediate evacuation of low-lying floodplains to designated shelters."
            elif danger_level > 0 and water_level >= danger_level * 0.9:
                risk_tier = "HIGH"
                should_trigger_alert = True
                headline = f"Orange Warning: Water Level Approaching Danger Threshold ({water_level}m)"
                action_advisory = "Place disaster response teams on active standby."

        elif ht == "EARTHQUAKE":
            mag = float(m.get("magnitude", 0.0))
            if mag >= 6.0:
                risk_tier = "EXTREME"
                should_trigger_alert = True
                headline = f"Major Earthquake Detected (Magnitude M{mag:.1f})"
                action_advisory = "Drop, Cover, and Hold On. Move away from unreinforced masonry."
            elif mag >= 4.5:
                risk_tier = "HIGH"
                should_trigger_alert = True
                headline = f"Moderate Seismological Event (Magnitude M{mag:.1f})"
                action_advisory = "Inspect premises for structural cracks and gas leaks."

        elif ht == "CYCLONE":
            wind = float(m.get("max_sustained_wind_kmh", 50.0))
            if wind >= 90.0:
                risk_tier = "EXTREME"
                should_trigger_alert = True
                headline = f"Severe Cyclonic Storm System (Sustained Gale {wind} km/h)"
                action_advisory = "Fishermen strictly prohibited at sea. Secure weak rooftops."
            else:
                risk_tier = "HIGH"
                should_trigger_alert = True
                headline = "Deep Depressive System Alert"
                action_advisory = "Monitor local meteorological bulletins continuously."

        return {
            "risk_level": risk_tier,
            "should_trigger_alert": should_trigger_alert,
            "headline": headline,
            "action_advisory": action_advisory
        }
