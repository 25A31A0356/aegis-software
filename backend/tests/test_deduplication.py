"""
AEGIS UNIFIED DATA CORE - Spatio-Temporal Deduplication Tests
"""
from datetime import datetime, timezone, timedelta
import pytest
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.ingestion.deduplicator import EventDeduplicator


def test_haversine_distance():
    # Distance between Mumbai (19.0760, 72.8777) and Pune (18.5204, 73.8567) is ~120 km
    dist = EventDeduplicator.haversine_distance_km(19.0760, 72.8777, 18.5204, 73.8567)
    assert 110.0 < dist < 130.0


def test_duplicate_event_clustering():
    now = datetime.now(timezone.utc)
    
    # Event 1: USGS Earthquake at (28.61, 77.20)
    event1 = UnifiedObservation(
        id="usgs-eq-1",
        hazard_type="EARTHQUAKE",
        location=GeoLocation(latitude=28.6139, longitude=77.2090),
        observed_at=now,
        received_at=now,
        measurements={"magnitude": 4.5}
    )

    # Event 2: IMD Regional Seismology reporting same event 5km away, 2 mins later
    event2 = UnifiedObservation(
        id="imd-eq-1",
        hazard_type="EARTHQUAKE",
        location=GeoLocation(latitude=28.6300, longitude=77.2200),
        observed_at=now + timedelta(minutes=2),
        received_at=now + timedelta(minutes=2),
        measurements={"magnitude": 4.6}
    )

    is_dupe, correlated = EventDeduplicator.is_duplicate_event(event2, [event1], max_distance_km=30.0, max_time_diff_sec=1800.0)
    assert is_dupe is True
    assert correlated is not None
    assert correlated.id == "usgs-eq-1"


def test_distinct_events_not_merged():
    now = datetime.now(timezone.utc)
    
    # Event 1: Delhi Earthquake
    event1 = UnifiedObservation(
        id="eq-delhi",
        hazard_type="EARTHQUAKE",
        location=GeoLocation(latitude=28.6139, longitude=77.2090),
        observed_at=now,
        received_at=now,
    )

    # Event 2: Gujarat Earthquake (800 km away)
    event2 = UnifiedObservation(
        id="eq-gujarat",
        hazard_type="EARTHQUAKE",
        location=GeoLocation(latitude=23.2420, longitude=69.6669),
        observed_at=now,
        received_at=now,
    )

    is_dupe, correlated = EventDeduplicator.is_duplicate_event(event2, [event1], max_distance_km=30.0)
    assert is_dupe is False
    assert correlated is None
