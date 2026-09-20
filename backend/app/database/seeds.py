"""
AEGIS UNIFIED DATA CORE - Database Baseline Seeding Script
Bootstraps official data sources, pre-configured field mappings, verified baseline alerts,
shelters/safe zones, and canonical emergency services directory in PostgreSQL.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from backend.app.database.session import async_session_factory
from backend.app.database.models import DataSource, FieldMapping, AlertRecord, SafeZone, EmergencyServiceEntity
from backend.app.core.encryption import SecretVault
from backend.app.core.config import settings
from backend.app.utils.logger import logger
from backend.app.api.v1.emergency_services import CANONICAL_NATIONAL_SERVICES


DEFAULT_SOURCES = [
    {
        "name": "Open-Meteo Meteorological Telemetry",
        "provider_code": "open_meteo",
        "category": "WEATHER",
        "base_url": "https://api.open-meteo.com/v1",
        "endpoint": "/forecast",
        "auth_type": "NONE",
        "response_format": "JSON",
        "update_frequency_minutes": 5,
        "cache_duration_seconds": 300,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": [
            {"external_field_path": "current.temperature_2m", "aegis_field_name": "temperature_c", "source_unit": "celsius", "target_unit": "°C"},
            {"external_field_path": "current.relative_humidity_2m", "aegis_field_name": "humidity_percent", "source_unit": "standard", "target_unit": "%"},
            {"external_field_path": "current.wind_speed_10m", "aegis_field_name": "wind_speed_kmh", "source_unit": "km/h", "target_unit": "km/h"},
            {"external_field_path": "current.surface_pressure", "aegis_field_name": "pressure_hpa", "source_unit": "hpa", "target_unit": "hPa"},
        ]
    },
    {
        "name": "USGS Real-Time Earthquake Hazards Feed",
        "provider_code": "usgs",
        "category": "EARTHQUAKE",
        "base_url": "https://earthquake.usgs.gov",
        "endpoint": "/earthquakes/feed/v1.0/summary/2.5_day.geojson",
        "auth_type": "NONE",
        "response_format": "GEOJSON",
        "update_frequency_minutes": 2,
        "cache_duration_seconds": 120,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": [
            {"external_field_path": "properties.mag", "aegis_field_name": "magnitude", "source_unit": "standard", "target_unit": "M"},
            {"external_field_path": "properties.place", "aegis_field_name": "location_name", "source_unit": "standard", "target_unit": "standard"},
            {"external_field_path": "geometry.coordinates.0", "aegis_field_name": "longitude", "source_unit": "standard", "target_unit": "deg"},
            {"external_field_path": "geometry.coordinates.1", "aegis_field_name": "latitude", "source_unit": "standard", "target_unit": "deg"},
        ]
    },
    {
        "name": "IMD Cyclone & Severe Weather Bulletins",
        "provider_code": "imd",
        "category": "CYCLONE",
        "base_url": "https://mausam.imd.gov.in",
        "endpoint": "/api/v1/telemetry",
        "auth_type": "NONE",
        "response_format": "JSON",
        "update_frequency_minutes": 5,
        "cache_duration_seconds": 300,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": [
            {"external_field_path": "max_sustained_wind_kmh", "aegis_field_name": "wind_speed_kmh", "source_unit": "km/h", "target_unit": "km/h"},
            {"external_field_path": "central_pressure_hpa", "aegis_field_name": "pressure_hpa", "source_unit": "hpa", "target_unit": "hPa"},
        ]
    },
    {
        "name": "Central Water Commission Hydro-Sensor Network",
        "provider_code": "cwc",
        "category": "FLOOD",
        "base_url": "https://ffs.india-water.gov.in",
        "endpoint": "/api/v1/hydro/stations",
        "auth_type": "NONE",
        "response_format": "JSON",
        "update_frequency_minutes": 5,
        "cache_duration_seconds": 300,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": [
            {"external_field_path": "water_level_m", "aegis_field_name": "water_level_m", "source_unit": "meter", "target_unit": "m"},
            {"external_field_path": "danger_level_m", "aegis_field_name": "danger_level_m", "source_unit": "meter", "target_unit": "m"},
        ]
    },
    {
        "name": "INCOIS Ocean State & Tsunami Early Warning",
        "provider_code": "incois",
        "category": "STORM",
        "base_url": "https://incois.gov.in",
        "endpoint": "/api/v1/ocean/bulletins",
        "auth_type": "NONE",
        "response_format": "JSON",
        "update_frequency_minutes": 10,
        "cache_duration_seconds": 600,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": []
    },
    {
        "name": "NASA FIRMS Satellite Wildfire Sensor",
        "provider_code": "nasa_firms",
        "category": "WILDFIRE",
        "base_url": "https://firms.modaps.eosdis.nasa.gov",
        "endpoint": "/api/area/csv",
        "auth_type": "NONE",
        "response_format": "CSV",
        "update_frequency_minutes": 15,
        "cache_duration_seconds": 900,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": []
    },
    {
        "name": "CPCB Ambient Air Quality Index Network",
        "provider_code": "cpcb",
        "category": "AIR_QUALITY",
        "base_url": "https://air-quality-api.open-meteo.com/v1",
        "endpoint": "/air-quality",
        "auth_type": "NONE",
        "response_format": "JSON",
        "update_frequency_minutes": 10,
        "cache_duration_seconds": 600,
        "is_enabled": True,
        "health_status": "HEALTHY",
        "mappings": []
    }
]

DEFAULT_ALERTS = [
    {
        "alert_code": "ALT-IMD-2026-0891",
        "hazard_type": "FLOOD",
        "severity": "critical",
        "status": "active",
        "headline": "Red Warning: Severe Convective Rainfall & Urban Inundation",
        "description": "IMD Doppler Radar confirms extreme convective precipitation (>115 mm/hr) over coastal belt with severe urban waterlogging risk.",
        "instruction": "Move to higher ground. Avoid low-lying subways, coastal causeways, and flooded underpasses.",
        "state_name": "Maharashtra",
        "district_name": "Mumbai Suburban",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "radius_km": 35.0,
        "source_agency": "India Meteorological Department (IMD)",
        "bulletin_id": "IMD-BULL-0891",
    },
    {
        "alert_code": "ALT-CWC-2026-0412",
        "hazard_type": "FLOOD",
        "severity": "warning",
        "status": "active",
        "headline": "Orange Alert: Godavari River Level Exceeding Danger Threshold",
        "description": "Central Water Commission hydro-sensors confirm rapid inflow surge (+18 cm/hr) across downstream Godavari river sectors.",
        "instruction": "Evacuate riverbank settlements to designated high-elevation disaster relief shelters.",
        "state_name": "Telangana",
        "district_name": "Bhadradri Kothagudem",
        "latitude": 17.5500,
        "longitude": 80.6200,
        "radius_km": 60.0,
        "source_agency": "Central Water Commission (CWC)",
        "bulletin_id": "CWC-HYD-0412",
    },
    {
        "alert_code": "ALT-IMD-2026-0774",
        "hazard_type": "CYCLONE",
        "severity": "critical",
        "status": "active",
        "headline": "Cyclone Watch: Severe Tropical Storm System Track",
        "description": "Deep depression over Bay of Bengal intensifies with squally gale winds up to 95 km/h on trajectory towards coastal Odisha.",
        "instruction": "Complete rooftop reinforcement. Fishermen strictly prohibited from venturing into open seas.",
        "state_name": "Odisha",
        "district_name": "Puri",
        "latitude": 19.8135,
        "longitude": 85.8312,
        "radius_km": 120.0,
        "source_agency": "IMD Cyclone Warning Division",
        "bulletin_id": "IMD-CYC-0774",
    },
    {
        "alert_code": "ALT-USGS-2026-0182",
        "hazard_type": "EARTHQUAKE",
        "severity": "warning",
        "status": "monitoring",
        "headline": "Seismic Watch: M5.4 Earthquake Epicenter Relaxation",
        "description": "National Seismological Network recorded M5.4 event at focal depth 12 km. Structural assessment underway.",
        "instruction": "Drop, Cover, and Hold On during aftershocks. Inspect gas connections and structural masonry.",
        "state_name": "Assam",
        "district_name": "Guwahati Sector",
        "latitude": 26.1445,
        "longitude": 91.7362,
        "radius_km": 80.0,
        "source_agency": "USGS / National Center for Seismology",
        "bulletin_id": "NCS-SEIS-0182",
    }
]

DEFAULT_SHELTERS = [
    {
        "name": "Gopalpur Multi-Purpose Cyclone Shelter (ODRAF Zone 4)",
        "zone_type": "RELIEF_SHELTER",
        "latitude": 19.2612,
        "longitude": 84.8634,
        "capacity": 2500,
        "current_occupancy": 320,
        "address": "Near Marine Police Station, Gopalpur-on-Sea",
        "city": "Gopalpur",
        "district": "Ganjam",
        "state": "Odisha",
        "contact_phone": "+91 680 2242100",
        "amenities": ["FOOD", "WATER", "MEDICAL", "SOLAR_BACKUP", "HIGH_ELEVATION"]
    },
    {
        "name": "Puri Jagannath Coastal Evacuation Center",
        "zone_type": "EVACUATION_CENTER",
        "latitude": 19.8135,
        "longitude": 85.8312,
        "capacity": 3000,
        "current_occupancy": 450,
        "address": "VIP Road, Near District Collectorate",
        "city": "Puri",
        "district": "Puri",
        "state": "Odisha",
        "contact_phone": "+91 6752 222034",
        "amenities": ["FOOD", "WATER", "POWER", "COMMUNITY_KITCHEN"]
    },
    {
        "name": "Bhadradri Flood Relief Camp & Medical Hub",
        "zone_type": "RELIEF_SHELTER",
        "latitude": 17.5500,
        "longitude": 80.6200,
        "capacity": 1800,
        "current_occupancy": 150,
        "address": "High School Grounds, Temple Road",
        "city": "Bhadrachalam",
        "district": "Bhadradri Kothagudem",
        "state": "Telangana",
        "contact_phone": "+91 8743 232444",
        "amenities": ["FOOD", "WATER", "MEDICAL", "BOATS"]
    },
    {
        "name": "Kurla Municipal Relief Shelter & Community Center",
        "zone_type": "RELIEF_SHELTER",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "capacity": 1200,
        "current_occupancy": 80,
        "address": "LBS Marg, Kurla West",
        "city": "Mumbai",
        "district": "Mumbai Suburban",
        "state": "Maharashtra",
        "contact_phone": "+91 22 26500000",
        "amenities": ["WATER", "MEDICAL", "DEWATERING_PUMPS"]
    },
    {
        "name": "AIIMS Emergency Trauma & Disaster Medicine Center (Delhi)",
        "zone_type": "HOSPITAL",
        "latitude": 28.5672,
        "longitude": 77.2100,
        "capacity": 800,
        "current_occupancy": 610,
        "address": "Sri Aurobindo Marg, Ansari Nagar",
        "city": "New Delhi",
        "district": "South Delhi",
        "state": "Delhi NCR",
        "contact_phone": "102 / 011-26588500",
        "amenities": ["ICU", "TRAUMA_SURGERY", "BLOOD_BANK", "HELIPAD", "OXYGEN"]
    },
    {
        "name": "KEM Hospital Disaster & Emergency Response Wing (Mumbai)",
        "zone_type": "HOSPITAL",
        "latitude": 19.0024,
        "longitude": 72.8427,
        "capacity": 650,
        "current_occupancy": 490,
        "address": "Acharya Donde Marg, Parel",
        "city": "Mumbai",
        "district": "Mumbai City",
        "state": "Maharashtra",
        "contact_phone": "108 / 022-24107000",
        "amenities": ["ICU", "TRAUMA_CARE", "BURN_UNIT", "AMBULANCE_BASE"]
    },
    {
        "name": "Gandhi Hospital Critical Care & Emergency Unit (Hyderabad)",
        "zone_type": "HOSPITAL",
        "latitude": 17.4239,
        "longitude": 78.5033,
        "capacity": 500,
        "current_occupancy": 380,
        "address": "Musheerabad, Padmarao Nagar",
        "city": "Hyderabad",
        "district": "Hyderabad",
        "state": "Telangana",
        "contact_phone": "108 / 040-27505566",
        "amenities": ["TRAUMA_CARE", "ICU", "BLOOD_BANK", "DISASTER_TRIAGE"]
    }
]


async def seed_database():
    """Seeds default providers, field mappings, verified alerts, shelters, and emergency services."""
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        # 1. Seed Data Sources
        for src_data in DEFAULT_SOURCES:
            stmt = select(DataSource).where(DataSource.provider_code == src_data["provider_code"])
            res = await session.execute(stmt)
            existing = res.scalars().first()
            if not existing:
                api_key_val = None
                p_code = src_data["provider_code"]
                if p_code == "nasa_firms" and getattr(settings, "NASA_FIRMS_MAP_KEY", None):
                    api_key_val = settings.NASA_FIRMS_MAP_KEY
                elif p_code == "imd" and getattr(settings, "IMD_API_KEY", None):
                    api_key_val = settings.IMD_API_KEY
                elif p_code == "cwc" and getattr(settings, "CWC_API_KEY", None):
                    api_key_val = settings.CWC_API_KEY
                elif p_code == "cpcb" and getattr(settings, "CPCB_API_KEY", None):
                    api_key_val = settings.CPCB_API_KEY

                encrypted_key = SecretVault.encrypt_secret(api_key_val) if api_key_val else None

                source = DataSource(
                    name=src_data["name"],
                    provider_code=src_data["provider_code"],
                    category=src_data["category"],
                    base_url=src_data["base_url"],
                    endpoint=src_data["endpoint"],
                    auth_type="API_KEY" if encrypted_key else src_data["auth_type"],
                    encrypted_api_key=encrypted_key,
                    response_format=src_data["response_format"],
                    update_frequency_minutes=src_data["update_frequency_minutes"],
                    cache_duration_seconds=src_data["cache_duration_seconds"],
                    is_enabled=src_data["is_enabled"],
                    health_status=src_data["health_status"]
                )
                session.add(source)
                await session.flush()

                raw_mappings = src_data.get("mappings")
                if isinstance(raw_mappings, list):
                    for m in raw_mappings:
                        if isinstance(m, dict):
                            mapping = FieldMapping(
                                data_source_id=source.id,
                                external_field_path=str(m.get("external_field_path", "")),
                                aegis_field_name=str(m.get("aegis_field_name", "")),
                                source_unit=str(m.get("source_unit", "")),
                                target_unit=str(m.get("target_unit", "")),
                                transformation_rule="direct"
                            )
                            session.add(mapping)
                logger.info(f"Seeded default provider: {src_data['name']}")

        # 2. Seed Alerts
        for a_data in DEFAULT_ALERTS:
            stmt = select(AlertRecord).where(AlertRecord.alert_code == a_data["alert_code"])
            res = await session.execute(stmt)
            if not res.scalars().first():
                alert = AlertRecord(
                    alert_code=a_data["alert_code"],
                    hazard_type=a_data["hazard_type"],
                    severity=a_data["severity"],
                    status=a_data["status"],
                    headline=a_data["headline"],
                    description=a_data["description"],
                    instruction=a_data["instruction"],
                    state_name=a_data["state_name"],
                    district_name=a_data["district_name"],
                    latitude=a_data["latitude"],
                    longitude=a_data["longitude"],
                    radius_km=a_data["radius_km"],
                    source_agency=a_data["source_agency"],
                    bulletin_id=a_data["bulletin_id"],
                    published_at=now - timedelta(minutes=15),
                    valid_until=now + timedelta(hours=12),
                    provenance_type="official_warning"
                )
                session.add(alert)
                logger.info(f"Seeded alert: {a_data['alert_code']}")

        # 3. Seed Shelters & Safe Zones
        for sh in DEFAULT_SHELTERS:
            stmt = select(SafeZone).where(SafeZone.name == sh["name"])
            res = await session.execute(stmt)
            if not res.scalars().first():
                sz = SafeZone(
                    name=sh["name"],
                    zone_type=sh["zone_type"],
                    latitude=sh["latitude"],
                    longitude=sh["longitude"],
                    capacity=sh["capacity"],
                    current_occupancy=sh["current_occupancy"],
                    address=sh["address"],
                    city=sh["city"],
                    district=sh["district"],
                    state=sh["state"],
                    contact_phone=sh["contact_phone"],
                    is_active=True,
                    amenities=sh["amenities"]
                )
                session.add(sz)
                logger.info(f"Seeded safe zone/shelter: {sh['name']}")

        # 4. Seed Canonical Emergency Services Directory
        for srv in CANONICAL_NATIONAL_SERVICES:
            stmt = select(EmergencyServiceEntity).where(EmergencyServiceEntity.service_code == srv["service_code"])
            res = await session.execute(stmt)
            if not res.scalars().first():
                entity = EmergencyServiceEntity(
                    service_code=srv["service_code"],
                    name=srv["name"],
                    category=srv["category"],
                    phone_numbers=srv["phone_numbers"],
                    alternate_phone=srv.get("alternate_phone", ""),
                    state=srv.get("state", "All India"),
                    district=srv.get("district", "All Districts"),
                    action_types=srv.get("action_types", ["CALL", "SMS"]),
                    description=srv["description"],
                    is_automated_dispatch_integrated=srv.get("is_automated_dispatch_integrated", False),
                    dispatch_endpoint=srv.get("dispatch_endpoint", ""),
                    is_active=True,
                    display_priority=srv.get("display_priority", 10)
                )
                session.add(entity)
                logger.info(f"Seeded emergency service: {srv['service_code']}")

        await session.commit()
        logger.info("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
