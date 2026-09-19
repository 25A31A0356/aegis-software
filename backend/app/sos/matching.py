"""
AEGIS UNIFIED DATA CORE - SOS Geospatial Matching Engine
Performs 10 km initial and 20 km expanded geospatial responder discovery using PostGIS / Spherical Spatial Queries.
Enforces active opt-in, availability, and concurrency eligibility rules.
"""
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, not_
from backend.app.database.models import (
    SOSSignal, SOSResponderCandidate, User, UserPreference, SOSAssignment, utc_now
)
from backend.app.core.config import settings
from backend.app.utils.logger import logger


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance in kilometers between two GPS coordinates."""
    r = 6371.0  # Earth mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class SOSMatchingEngine:
    """
    Finds and assigns eligible nearby citizen responders to active SOS incidents.
    """

    @classmethod
    async def get_busy_responder_ids(cls, db: AsyncSession) -> List[str]:
        """Returns IDs of responders currently handling active SOS incidents."""
        active_assignments_query = select(SOSAssignment.responder_user_id).where(
            SOSAssignment.status == "ACTIVE"
        )
        res = await db.execute(active_assignments_query)
        busy_ids = [row[0] for row in res.fetchall() if row[0]]
        return busy_ids

    @classmethod
    async def find_eligible_responders(
        cls,
        db: AsyncSession,
        sos: SOSSignal,
        initial_radius_km: Optional[float] = None,
        max_radius_km: Optional[float] = None,
        max_candidates: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes two-tier radius search:
        1. Search within initial_radius_km (default 10 km)
        2. If < 1 candidate found, expand up to max_radius_km (default 20 km)
        """
        r_init = initial_radius_km or settings.SOS_INITIAL_RADIUS_KM
        r_max = max_radius_km or settings.SOS_MAX_RADIUS_KM
        limit = max_candidates or settings.SOS_MAX_CANDIDATES

        sos_lat = sos.latitude
        sos_lon = sos.longitude
        requester_id = sos.requester_user_id or sos.user_id

        # 1. Exclude busy responders
        busy_ids = await cls.get_busy_responder_ids(db)

        # 2. Query all active users who opted in and are available
        query = (
            select(User, UserPreference)
            .join(UserPreference, User.id == UserPreference.user_id)
            .where(
                User.is_active == True,
                UserPreference.is_responder_opted_in == True,
                UserPreference.is_available == True,
                UserPreference.last_known_lat != None,
                UserPreference.last_known_lng != None
            )
        )

        if requester_id:
            query = query.where(User.id != requester_id)
        if busy_ids:
            query = query.where(not_(User.id.in_(busy_ids)))

        res = await db.execute(query)
        rows = res.all()

        # 3. Calculate spatial distances
        tier_1_candidates: List[Dict[str, Any]] = []
        tier_2_candidates: List[Dict[str, Any]] = []

        for user_obj, pref_obj in rows:
            u_lat = pref_obj.last_known_lat
            u_lng = pref_obj.last_known_lng
            if u_lat is None or u_lng is None:
                continue

            dist_km = haversine_distance_km(sos_lat, sos_lon, u_lat, u_lng)

            candidate_data = {
                "user_id": user_obj.id,
                "email": user_obj.email,
                "full_name": user_obj.full_name or "Aegis Volunteer",
                "role": user_obj.role,
                "latitude": u_lat,
                "longitude": u_lng,
                "distance_km": round(dist_km, 2),
                "last_location_time": pref_obj.last_location_time.isoformat() if pref_obj.last_location_time else None
            }

            if dist_km <= r_init:
                tier_1_candidates.append(candidate_data)
            elif dist_km <= r_max:
                tier_2_candidates.append(candidate_data)

        # Sort candidates closest first
        tier_1_candidates.sort(key=lambda x: x["distance_km"])
        tier_2_candidates.sort(key=lambda x: x["distance_km"])

        selected_candidates: List[Dict[str, Any]] = []
        if tier_1_candidates:
            selected_candidates = tier_1_candidates[:limit]
            logger.info(f"SOS {sos.id} matched {len(selected_candidates)} responders in 10 km initial radius")
        elif tier_2_candidates:
            selected_candidates = tier_2_candidates[:limit]
            logger.info(f"SOS {sos.id} expanded search to 20 km and found {len(selected_candidates)} responders")
        else:
            logger.warning(f"SOS {sos.id} found 0 nearby eligible responders within {r_max} km")

        # 4. Save candidates to database
        for cand in selected_candidates:
            existing_candidate_res = await db.execute(
                select(SOSResponderCandidate).where(
                    SOSResponderCandidate.sos_id == sos.id,
                    SOSResponderCandidate.responder_user_id == cand["user_id"]
                )
            )
            existing_candidate = existing_candidate_res.scalars().first()

            if not existing_candidate:
                new_cand = SOSResponderCandidate(
                    sos_id=sos.id,
                    responder_user_id=cand["user_id"],
                    status="OFFERED",
                    distance_km=cand["distance_km"],
                    offered_at=utc_now()
                )
                db.add(new_cand)
            else:
                existing_candidate.status = "OFFERED"
                existing_candidate.distance_km = cand["distance_km"]
                existing_candidate.offered_at = utc_now()

        await db.commit()
        return selected_candidates
