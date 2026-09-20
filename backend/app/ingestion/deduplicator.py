"""
AEGIS UNIFIED DATA CORE - Spatio-Temporal Event Deduplication Engine
Clusters multi-source incoming observations (e.g. USGS + Regional Seismological Feed)
to recognize correlated events while strictly preserving independent source identities and authorities.
"""
import math
from typing import List, Tuple, Optional
from backend.app.schemas.unified import UnifiedObservation


class EventDeduplicator:
    @staticmethod
    def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates distance in km between two geo coordinates using Haversine formula."""
        R = 6371.0  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    @classmethod
    def is_duplicate_event(
        cls,
        new_obs: UnifiedObservation,
        existing_obs_list: List[UnifiedObservation],
        max_distance_km: float = 30.0,
        max_time_diff_sec: float = 1800.0  # 30 mins
    ) -> Tuple[bool, Optional[UnifiedObservation]]:
        """
        Determines if new_obs represents the same physical event as an existing observation.
        Returns (is_duplicate, correlated_existing_observation).
        """
        for existing in existing_obs_list:
            if existing.hazard_type != new_obs.hazard_type:
                continue

            # Check time delta
            time_diff = abs((new_obs.observed_at - existing.observed_at).total_seconds())
            if time_diff > max_time_diff_sec:
                continue

            # Check spatial distance
            dist = cls.haversine_distance_km(
                new_obs.location.latitude,
                new_obs.location.longitude,
                existing.location.latitude,
                existing.location.longitude
            )
            if dist <= max_distance_km:
                return True, existing

        return False, None
