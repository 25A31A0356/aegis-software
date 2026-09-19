"""
AEGIS UNIFIED DATA CORE - Multi-Hazard Classification Engine
Classifies external telemetry feeds and alerts into standardized AEGIS hazard categories.
Supported Core: WEATHER, EARTHQUAKE, FLOOD, CYCLONE, STORM, LIGHTNING, WILDFIRE, AIR_QUALITY, DISASTER_ALERT, OTHER.
Future Extensible: LANDSLIDE, TSUNAMI, DROUGHT, HEATWAVE, COLDWAVE, VOLCANIC.
"""
from typing import List, Optional


HAZARD_CATEGORIES = [
    "WEATHER",
    "EARTHQUAKE",
    "FLOOD",
    "CYCLONE",
    "STORM",
    "LIGHTNING",
    "WILDFIRE",
    "AIR_QUALITY",
    "DISASTER_ALERT",
    "LANDSLIDE",
    "TSUNAMI",
    "HEATWAVE",
    "DROUGHT",
    "OTHER"
]


class HazardClassifier:
    CATEGORY_KEYWORDS = {
        "CYCLONE": ["cyclone", "depression", "tropical storm", "typhoon", "landfall", "hurricane"],
        "FLOOD": ["flood", "inundation", "river level", "barrage", "water level", "cwc", "discharge", "submerged"],
        "EARTHQUAKE": ["earthquake", "seismic", "magnitude", "richter", "tremor", "epicenter", "hypocenter", "usgs"],
        "WILDFIRE": ["wildfire", "forest fire", "thermal anomaly", "firms", "viirs", "modis", "fire hotspot"],
        "AIR_QUALITY": ["aqi", "air quality", "pm2.5", "pm10", "cpcb", "pollution", "smog"],
        "LIGHTNING": ["lightning", "thunderbolt", "convective storm", "cloud to ground"],
        "TSUNAMI": ["tsunami", "sea wave", "incois ocean warning", "ocean surge"],
        "WEATHER": ["weather", "temperature", "forecast", "precipitation", "rain", "wind", "humidity", "open-meteo", "imd"]
    }

    @classmethod
    def classify(cls, text_or_metadata: str, default: str = "OTHER") -> str:
        """Classifies text, bulletin title or metadata into standardized AEGIS category."""
        if not text_or_metadata:
            return default

        lower = text_or_metadata.lower()
        for cat, keywords in cls.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    return cat

        return default.upper() if default.upper() in HAZARD_CATEGORIES else "OTHER"
