"""
AEGIS UNIFIED DATA CORE - Multi-Source Correlation Engine
Fuses multi-hazard telemetry (e.g. Rainfall Telemetry + River Level + Coastal Swell + Wind Gale)
into unified spatial hazard zones without destroying original provider observations.
"""
from typing import List
from datetime import datetime, timezone
from backend.app.schemas.unified import UnifiedObservation, GeoLocation, RiskEvaluationResponse


class CorrelationEngine:
    @classmethod
    def correlate_hazards_for_location(
        cls,
        lat: float,
        lng: float,
        observations: List[UnifiedObservation],
        radius_km: float = 100.0
    ) -> RiskEvaluationResponse:
        """
        Evaluates multi-source hazard observations surrounding (lat, lng)
        and computes a composite risk evaluation.
        """
        contributing_factors = []
        max_score = 10.0
        primary_hazard = "WEATHER"

        for obs in observations:
            m = obs.measurements
            ht = obs.hazard_type

            # Check individual hazard signals
            if ht == "WEATHER":
                precip = float(m.get("precipitation_mm", 0.0))
                wind = float(m.get("wind_speed_kmh", 0.0))
                temp = float(m.get("temperature_c", 25.0))
                if precip > 25.0 or wind > 50.0:
                    score = min(90.0, 30.0 + (precip * 1.5) + (wind * 0.5))
                    contributing_factors.append({
                        "hazard": "HEAVY_PRECIPITATION_GALE",
                        "source": obs.source_authority,
                        "intensity_score": score,
                        "description": f"Precipitation: {precip}mm/hr, Wind: {wind}km/h"
                    })
                    if score > max_score:
                        max_score = score
                        primary_hazard = "FLOOD" if precip > 35.0 else "WEATHER"

            elif ht == "FLOOD":
                water_level = float(m.get("water_level_m", 0.0))
                danger_level = float(m.get("danger_level_m", 1.0))
                if danger_level > 0 and water_level >= danger_level * 0.9:
                    score = min(98.0, 50.0 + ((water_level / danger_level) * 40.0))
                    contributing_factors.append({
                        "hazard": "RIVER_INUNDATION",
                        "source": obs.source_authority,
                        "intensity_score": score,
                        "description": f"River gauge level {water_level}m near/exceeding danger mark {danger_level}m"
                    })
                    if score > max_score:
                        max_score = score
                        primary_hazard = "FLOOD"

            elif ht == "CYCLONE":
                wind = float(m.get("max_sustained_wind_kmh", 60.0))
                score = min(100.0, 40.0 + (wind * 0.6))
                contributing_factors.append({
                    "hazard": "TROPICAL_CYCLONE",
                    "source": obs.source_authority,
                    "intensity_score": score,
                    "description": f"Tropical cyclonic storm track: max winds {wind}km/h"
                })
                if score > max_score:
                    max_score = score
                    primary_hazard = "CYCLONE"

            elif ht == "EARTHQUAKE":
                mag = float(m.get("magnitude", 3.0))
                score = min(100.0, (mag / 8.0) * 100.0)
                contributing_factors.append({
                    "hazard": "SEISMIC_EVENT",
                    "source": obs.source_authority,
                    "intensity_score": score,
                    "description": f"Magnitude {mag:.1f} seismic event detected"
                })
                if score > max_score:
                    max_score = score
                    primary_hazard = "EARTHQUAKE"

            elif ht == "WILDFIRE":
                frp = float(m.get("fire_radiative_power_mw", 20.0))
                score = min(95.0, 30.0 + (frp * 0.5))
                contributing_factors.append({
                    "hazard": "THERMAL_HOTSPOT",
                    "source": obs.source_authority,
                    "intensity_score": score,
                    "description": f"Satellite thermal anomaly detected: FRP {frp}MW"
                })
                if score > max_score:
                    max_score = score
                    primary_hazard = "WILDFIRE"

        # Determine composite risk level
        if max_score >= 80.0:
            risk_level = "EXTREME"
        elif max_score >= 60.0:
            risk_level = "VERY_HIGH"
        elif max_score >= 40.0:
            risk_level = "HIGH"
        elif max_score >= 20.0:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        return RiskEvaluationResponse(
            location=GeoLocation(latitude=lat, longitude=lng),
            composite_risk_score=round(max_score, 1),
            risk_level=risk_level,
            primary_hazard=primary_hazard,
            contributing_factors=contributing_factors,
            is_aegis_derived=True,
            provenance="AEGIS Multi-Source Correlation Engine",
            evaluated_at=datetime.now(timezone.utc).isoformat()
        )
