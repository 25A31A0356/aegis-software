"""
AEGIS UNIFIED DATA CORE - SOS Multi-Factor Geospatial Matching Engine
Performs intelligent, deterministic multi-factor responder discovery across:
- Proximity / Great-Circle Distance (10 km initial, 20 km expansion)
- Real-time Availability & Opt-in Status
- Specialized Capabilities & Certifications matching Emergency Category
- Current Operational Workload & Concurrency Limits
- GPS Telemetry Freshness & Stale Location Penalization

Zero Random Selection: All candidates are deterministically ranked via weighted composite score.
"""
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, not_
from backend.app.database.models import (
    SOSSignal, SOSResponderCandidate, User, UserPreference, SOSAssignment, utc_now
)
from backend.app.core.config import settings
from backend.app.utils.logger import logger


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle spherical distance in kilometers between two GPS coordinates."""
    r = 6371.0  # Earth mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


EMERGENCY_REQUIRED_CAPABILITIES: Dict[str, List[str]] = {
    "medical": ["FIRST_AID", "PARAMEDIC", "DOCTOR", "NURSE", "MEDICAL_EMERGENCY"],
    "medical_emergency": ["FIRST_AID", "PARAMEDIC", "DOCTOR", "NURSE", "MEDICAL_EMERGENCY"],
    "flood_trapped": ["BOAT_RESCUE", "SWIMMER", "SEARCH_AND_RESCUE", "FLOOD_DISASTER"],
    "floods": ["BOAT_RESCUE", "SWIMMER", "SEARCH_AND_RESCUE", "FLOOD_DISASTER"],
    "fire": ["FIREFIGHTING", "SEARCH_AND_RESCUE", "SMOKE_EVACUATION"],
    "building_collapse": ["SEARCH_AND_RESCUE", "HEAVY_RESCUE", "FIRST_AID", "DOG_SQUAD"],
    "cyclone_shelter": ["COMMUNITY_EVACUATION", "FIRST_AID", "LOGISTICS"],
    "general": ["FIRST_AID", "COMMUNITY_VOLUNTEER", "GENERAL_ASSIST"]
}


class SOSMatchingEngine:
    """
    Evaluates and ranks nearby eligible responders using a deterministic multi-factor objective function.
    """

    @classmethod
    async def get_active_workload_map(cls, db: AsyncSession) -> Dict[str, int]:
        """Returns a mapping of responder_user_id -> count of currently ACTIVE SOS assignments."""
        active_query = select(
            SOSAssignment.responder_user_id,
            func.count(SOSAssignment.id).label("active_count")
        ).where(
            SOSAssignment.status == "ACTIVE"
        ).group_by(SOSAssignment.responder_user_id)
        
        res = await db.execute(active_query)
        return {row[0]: int(row[1]) for row in res.fetchall() if row[0]}

    @classmethod
    def evaluate_capability_match(cls, emergency_type: str, user_role: str, user_capabilities: List[str]) -> tuple[float, List[str]]:
        """
        Calculates capability alignment score between emergency requirement and responder qualifications.
        Returns: (score [0.0 - 1.0], list of matching capabilities)
        """
        clean_type = (emergency_type or "general").lower()
        required = EMERGENCY_REQUIRED_CAPABILITIES.get(clean_type, EMERGENCY_REQUIRED_CAPABILITIES["general"])
        user_caps_upper = [c.upper() for c in (user_capabilities or [])]

        # SDRF / NDRF / Official Command gets maximum capability score
        if user_role in ["sdrf_officer", "ndrf_officer", "admin", "official"]:
            return 1.0, ["OFFICIAL_TACTICAL_RESPONDER"] + [c for c in user_caps_upper if c in required]

        matched = [c for c in user_caps_upper if c in required]
        if matched:
            return 1.0, matched
        elif user_caps_upper:
            return 0.7, ["GENERAL_REGISTERED_SKILL"]
        else:
            return 0.5, ["BASIC_COMMUNITY_RESPONDER"]

    @classmethod
    def evaluate_gps_freshness(cls, last_location_time: Optional[datetime], now: datetime) -> tuple[float, bool, str, float]:
        """
        Calculates GPS freshness score, staleness badge, threshold status, and age in seconds.
        FRESH (< 2 min): 1.0
        RECENT (2 - 10 min): 0.75
        STALE (10 - 30 min): 0.40
        EXPIRED (> 30 min): 0.05
        UNKNOWN (missing): 0.05
        """
        if not last_location_time:
            return 0.05, False, "UNKNOWN", 999999.0

        # Normalize naive/aware datetimes across SQLite and PostgreSQL
        t_loc = last_location_time
        t_now = now
        if t_loc.tzinfo is None and t_now.tzinfo is not None:
            t_loc = t_loc.replace(tzinfo=t_now.tzinfo)
        elif t_loc.tzinfo is not None and t_now.tzinfo is None:
            t_now = t_now.replace(tzinfo=t_loc.tzinfo)

        age_seconds = max(0.0, (t_now - t_loc).total_seconds())

        if age_seconds <= 120:
            return 1.0, True, "FRESH", age_seconds
        elif age_seconds <= 600:
            return 0.75, True, "RECENT", age_seconds
        elif age_seconds <= 1800:
            return 0.40, False, "STALE", age_seconds
        else:
            return 0.05, False, "EXPIRED", age_seconds

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
        Executes multi-factor deterministic geospatial responder discovery.
        Scores every eligible candidate by:
        Score = 0.40 * Proximity + 0.30 * Capability + 0.20 * GPS Freshness + 0.10 * Workload
        """
        r_init = initial_radius_km or settings.SOS_INITIAL_RADIUS_KM
        r_max = max_radius_km or settings.SOS_MAX_RADIUS_KM
        limit = max_candidates or settings.SOS_MAX_CANDIDATES

        sos_lat = sos.latitude
        sos_lon = sos.longitude
        requester_id = sos.requester_user_id or sos.user_id
        now = utc_now()

        # 1. Fetch current active workloads
        workload_map = await cls.get_active_workload_map(db)

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

        res = await db.execute(query)
        rows = res.all()

        tier_1_candidates: List[Dict[str, Any]] = []
        tier_2_candidates: List[Dict[str, Any]] = []

        for user_obj, pref_obj in rows:
            u_lat = pref_obj.last_known_lat
            u_lng = pref_obj.last_known_lng
            if u_lat is None or u_lng is None:
                continue

            # Workload check: Exclude responders at maximum capacity
            active_count = workload_map.get(user_obj.id, 0)
            max_assignments = max(1, getattr(pref_obj, "max_active_assignments", 1))
            if active_count >= max_assignments:
                continue

            dist_km = haversine_distance_km(sos_lat, sos_lon, u_lat, u_lng)

            # Check if within max radius
            if dist_km > r_max:
                continue

            # Multi-factor score components:
            # 1. Proximity Score (0.0 to 1.0)
            s_dist = max(0.0, 1.0 - (dist_km / r_max))

            # 2. Capability Score (0.0 to 1.0)
            user_caps = getattr(pref_obj, "capabilities", []) or []
            s_cap, matched_skills = cls.evaluate_capability_match(sos.emergency_type, user_obj.role, user_caps)

            # 3. GPS Freshness Score (0.0 to 1.0)
            s_fresh, is_gps_fresh, gps_freshness_status, age_sec = cls.evaluate_gps_freshness(pref_obj.last_location_time, now)

            # 4. Workload Score (0.0 to 1.0)
            s_work = max(0.0, 1.0 - (float(active_count) / float(max_assignments)))

            # Composite weighted score
            composite_score = round(
                (0.40 * s_dist) +
                (0.30 * s_cap) +
                (0.20 * s_fresh) +
                (0.10 * s_work),
                4
            )

            candidate_data = {
                "user_id": user_obj.id,
                "email": user_obj.email,
                "full_name": user_obj.full_name or "Aegis Volunteer",
                "role": user_obj.role,
                "latitude": u_lat,
                "longitude": u_lng,
                "distance_km": round(dist_km, 2),
                "distance_meters": round(dist_km * 1000.0, 1),
                "score": composite_score,
                "s_dist": round(s_dist, 3),
                "s_cap": round(s_cap, 3),
                "s_fresh": round(s_fresh, 3),
                "s_work": round(s_work, 3),
                "is_gps_fresh": is_gps_fresh,
                "gps_freshness_status": gps_freshness_status,
                "gps_age_seconds": round(age_sec, 1),
                "matched_skills": matched_skills,
                "vehicle_type": getattr(pref_obj, "vehicle_type", "MOTORCYCLE") or "MOTORCYCLE",
                "active_workload": active_count,
                "max_assignments": max_assignments,
                "last_location_time": pref_obj.last_location_time.isoformat() if pref_obj.last_location_time else None
            }

            if dist_km <= r_init:
                tier_1_candidates.append(candidate_data)
            else:
                tier_2_candidates.append(candidate_data)

        # Deterministic Ranking: Sort primarily by composite score descending, then distance ascending
        tier_1_candidates.sort(key=lambda x: (-x["score"], x["distance_km"]))
        tier_2_candidates.sort(key=lambda x: (-x["score"], x["distance_km"]))

        selected_candidates: List[Dict[str, Any]] = []
        if tier_1_candidates:
            selected_candidates = tier_1_candidates[:limit]
            logger.info(f"SOS {sos.id} matched {len(selected_candidates)} deterministic responders within {r_init} km (Top score: {selected_candidates[0]['score']})")
        elif tier_2_candidates:
            selected_candidates = tier_2_candidates[:limit]
            logger.info(f"SOS {sos.id} expanded search to {r_max} km and found {len(selected_candidates)} responders (Top score: {selected_candidates[0]['score']})")
        else:
            logger.warning(f"SOS {sos.id} found 0 nearby eligible responders within {r_max} km")

        # 5. Save/Update candidates in database
        for cand in selected_candidates:
            existing_candidate_res = await db.execute(
                select(SOSResponderCandidate).where(
                    SOSResponderCandidate.sos_id == sos.id,
                    SOSResponderCandidate.responder_user_id == cand["user_id"]
                )
            )
            existing_candidate = existing_candidate_res.scalars().first()

            age_str = f"{int(cand['gps_age_seconds'])}s" if cand['gps_age_seconds'] < 60 else f"{int(cand['gps_age_seconds'] / 60)}m"
            rationale = (
                f"Score: {cand['score']:.4f} | Dist: {cand['distance_km']}km | "
                f"Skills: {', '.join(cand['matched_skills'])} | "
                f"GPS: {cand['gps_freshness_status']} ({age_str} ago) | Workload: {cand['active_workload']}"
            )
            cand["selection_rationale"] = rationale

            if not existing_candidate:
                new_cand = SOSResponderCandidate(
                    sos_id=sos.id,
                    responder_user_id=cand["user_id"],
                    status="OFFERED",
                    distance_km=cand["distance_km"],
                    selection_rationale=rationale,
                    offered_at=utc_now()
                )
                db.add(new_cand)
            else:
                existing_candidate.status = "OFFERED"
                existing_candidate.distance_km = cand["distance_km"]
                existing_candidate.selection_rationale = rationale
                existing_candidate.offered_at = utc_now()

        await db.commit()
        return selected_candidates
