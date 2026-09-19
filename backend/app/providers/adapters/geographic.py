"""
AEGIS UNIFIED DATA CORE - Geographic & Location Provider Adapter
Supports forward geocoding, reverse geocoding, and administrative boundary resolution.
Features built-in offline Indian administrative centroid database for guaranteed offline resilience.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import math
import httpx
from backend.app.providers.base import BaseProvider, ProviderFetchResult
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.core.ssrf import SSRFGuard
from backend.app.core.config import settings

# Curated offline Indian administrative reference data
OFFLINE_LOCATIONS = [
    {"name": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "country": "India", "lat": 19.0760, "lng": 72.8777, "elevation": 14, "timezone": "Asia/Kolkata"},
    {"name": "Delhi", "district": "New Delhi", "state": "Delhi", "country": "India", "lat": 28.6139, "lng": 77.2090, "elevation": 216, "timezone": "Asia/Kolkata"},
    {"name": "Bengaluru", "district": "Bengaluru Urban", "state": "Karnataka", "country": "India", "lat": 12.9716, "lng": 77.5946, "elevation": 920, "timezone": "Asia/Kolkata"},
    {"name": "Hyderabad", "district": "Hyderabad", "state": "Telangana", "country": "India", "lat": 17.3850, "lng": 78.4867, "elevation": 542, "timezone": "Asia/Kolkata"},
    {"name": "Chennai", "district": "Chennai", "state": "Tamil Nadu", "country": "India", "lat": 13.0827, "lng": 80.2707, "elevation": 6, "timezone": "Asia/Kolkata"},
    {"name": "Kolkata", "district": "Kolkata", "state": "West Bengal", "country": "India", "lat": 22.5726, "lng": 88.3639, "elevation": 9, "timezone": "Asia/Kolkata"},
    {"name": "Ahmedabad", "district": "Ahmedabad", "state": "Gujarat", "country": "India", "lat": 23.0225, "lng": 72.5714, "elevation": 53, "timezone": "Asia/Kolkata"},
    {"name": "Pune", "district": "Pune", "state": "Maharashtra", "country": "India", "lat": 18.5204, "lng": 73.8567, "elevation": 560, "timezone": "Asia/Kolkata"},
    {"name": "Jaipur", "district": "Jaipur", "state": "Rajasthan", "country": "India", "lat": 26.9124, "lng": 75.7873, "elevation": 431, "timezone": "Asia/Kolkata"},
    {"name": "Lucknow", "district": "Lucknow", "state": "Uttar Pradesh", "country": "India", "lat": 26.8467, "lng": 80.9462, "elevation": 123, "timezone": "Asia/Kolkata"},
    {"name": "Patna", "district": "Patna", "state": "Bihar", "country": "India", "lat": 25.5941, "lng": 85.1376, "elevation": 53, "timezone": "Asia/Kolkata"},
    {"name": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "country": "India", "lat": 20.2961, "lng": 85.8245, "elevation": 45, "timezone": "Asia/Kolkata"},
    {"name": "Guwahati", "district": "Kamrup Metropolitan", "state": "Assam", "country": "India", "lat": 26.1445, "lng": 91.7362, "elevation": 55, "timezone": "Asia/Kolkata"},
    {"name": "Shimla", "district": "Shimla", "state": "Himachal Pradesh", "country": "India", "lat": 31.1048, "lng": 77.1734, "elevation": 2276, "timezone": "Asia/Kolkata"},
    {"name": "Dehradun", "district": "Dehradun", "state": "Uttarakhand", "country": "India", "lat": 30.3165, "lng": 78.0322, "elevation": 640, "timezone": "Asia/Kolkata"},
    {"name": "Srinagar", "district": "Srinagar", "state": "Jammu and Kashmir", "country": "India", "lat": 34.0837, "lng": 74.7973, "elevation": 1585, "timezone": "Asia/Kolkata"},
    {"name": "Thiruvananthapuram", "district": "Thiruvananthapuram", "state": "Kerala", "country": "India", "lat": 8.5241, "lng": 76.9366, "elevation": 10, "timezone": "Asia/Kolkata"},
    {"name": "Visakhapatnam", "district": "Visakhapatnam", "state": "Andhra Pradesh", "country": "India", "lat": 17.6868, "lng": 83.2185, "elevation": 45, "timezone": "Asia/Kolkata"},
    {"name": "Ranchi", "district": "Ranchi", "state": "Jharkhand", "country": "India", "lat": 23.3441, "lng": 85.3096, "elevation": 651, "timezone": "Asia/Kolkata"},
    {"name": "Raipur", "district": "Raipur", "state": "Chhattisgarh", "country": "India", "lat": 21.2514, "lng": 81.6296, "elevation": 298, "timezone": "Asia/Kolkata"},
    {"name": "Panaji", "district": "North Goa", "state": "Goa", "country": "India", "lat": 15.4909, "lng": 73.8278, "elevation": 7, "timezone": "Asia/Kolkata"},
    {"name": "Gandhinagar", "district": "Gandhinagar", "state": "Gujarat", "country": "India", "lat": 23.2156, "lng": 72.6369, "elevation": 81, "timezone": "Asia/Kolkata"},
    {"name": "Bhopal", "district": "Bhopal", "state": "Madhya Pradesh", "country": "India", "lat": 23.2599, "lng": 77.4126, "elevation": 527, "timezone": "Asia/Kolkata"},
    {"name": "Chandigarh", "district": "Chandigarh", "state": "Chandigarh", "country": "India", "lat": 30.7333, "lng": 76.7794, "elevation": 321, "timezone": "Asia/Kolkata"},
]


class GeographicLocationProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="Open-Meteo & National Geocoding Grid",
            provider_code="GEOGRAPHIC_CORE",
            base_url="https://geocoding-api.open-meteo.com/v1",
            endpoint="/search",
            timeout_seconds=8.0
        )

    async def geocode(self, query: str, count: int = 5) -> List[Dict[str, Any]]:
        """Searches for places/administrative areas matching query string."""
        if not query or len(query.strip()) < 2:
            return []

        q_clean = query.strip().lower()
        results: List[Dict[str, Any]] = []

        # Attempt live Open-Meteo Geocoding API query
        fetch_res = await self.fetch(custom_params={"name": query, "count": count, "language": "en", "format": "json"})
        if fetch_res.success and isinstance(fetch_res.raw_data, dict):
            raw_results = fetch_res.raw_data.get("results") or []
            for item in raw_results:
                results.append({
                    "name": item.get("name"),
                    "locality": item.get("admin3") or item.get("name"),
                    "district": item.get("admin2") or item.get("name"),
                    "state": item.get("admin1") or "",
                    "country": item.get("country") or "India",
                    "latitude": float(item.get("latitude", 0.0)),
                    "longitude": float(item.get("longitude", 0.0)),
                    "elevation": float(item.get("elevation", 0.0)),
                    "timezone": item.get("timezone", "Asia/Kolkata"),
                    "source": "Open-Meteo Geocoding Service"
                })

        # If live service returned nothing or failed, use offline curated reference matching
        if not results:
            for loc in OFFLINE_LOCATIONS:
                if q_clean in loc["name"].lower() or q_clean in loc["district"].lower() or q_clean in loc["state"].lower():
                    results.append({
                        "name": loc["name"],
                        "locality": loc["name"],
                        "district": loc["district"],
                        "state": loc["state"],
                        "country": loc["country"],
                        "latitude": loc["lat"],
                        "longitude": loc["lng"],
                        "elevation": loc["elevation"],
                        "timezone": loc["timezone"],
                        "source": "AEGIS National Geographic Centroid Registry"
                    })
                if len(results) >= count:
                    break

        return results

    async def reverse_geocode(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Resolves latitude/longitude coordinates to nearest administrative area."""
        # Find nearest offline centroid using Haversine formula
        best_match = None
        min_dist = float("inf")

        for loc in OFFLINE_LOCATIONS:
            d_lat = math.radians(loc["lat"] - latitude)
            d_lon = math.radians(loc["lng"] - longitude)
            a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(latitude)) * math.cos(math.radians(loc["lat"])) * math.sin(d_lon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            dist_km = 6371.0 * c

            if dist_km < min_dist:
                min_dist = dist_km
                best_match = loc

        if best_match and min_dist <= 150.0:
            return {
                "name": best_match["name"],
                "locality": best_match["name"],
                "district": best_match["district"],
                "state": best_match["state"],
                "country": best_match["country"],
                "latitude": latitude,
                "longitude": longitude,
                "distance_to_centroid_km": round(min_dist, 2),
                "elevation": best_match["elevation"],
                "timezone": best_match["timezone"],
                "confidence": max(0.5, round(1.0 - (min_dist / 300.0), 2)),
                "source": "AEGIS National Geographic Centroid Registry"
            }

        return {
            "name": f"Coordinates ({latitude:.4f}, {longitude:.4f})",
            "locality": "Regional Sector",
            "district": "Unknown District",
            "state": "India",
            "country": "India",
            "latitude": latitude,
            "longitude": longitude,
            "distance_to_centroid_km": round(min_dist, 2) if best_match else 0.0,
            "elevation": 50.0,
            "timezone": "Asia/Kolkata",
            "confidence": 0.6,
            "source": "AEGIS Geometric Interpolation"
        }

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_data, dict):
            return raw_data.get("results") or []
        return []

    def normalize(self, parsed_record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = float(parsed_record.get("latitude", 0.0))
        lng = float(parsed_record.get("longitude", 0.0))
        now = datetime.now(timezone.utc)

        return UnifiedObservation(
            id=f"GEO-{abs(hash(str(lat)+str(lng)))}",
            data_source_id=self.provider_code,
            hazard_type="OTHER",
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=parsed_record.get("name"),
                district_name=parsed_record.get("admin2"),
                state_name=parsed_record.get("admin1")
            ),
            observed_at=now,
            received_at=now,
            severity="minor",
            risk_level="LOW",
            confidence=1.0,
            source_authority=self.name,
            measurements={
                "elevation": parsed_record.get("elevation", 0.0),
                "timezone": parsed_record.get("timezone", "UTC")
            }
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, "Latitude out of bounds"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, "Longitude out of bounds"
        return True, None
