import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from backend.app.database.models import (
    SOSSignal, SOSAssignment, SOSLocationUpdate,
    User, UserPreference, SafeZone, IncidentReport,
    NormalizedObservation, AlertRecord, utc_now
)


@pytest.mark.asyncio
async def test_01_zero_fake_markers_on_empty_database(async_client: AsyncClient, test_db: AsyncSession):
    """
    Validates the strict Zero Fake Markers constraint.
    If database tables are empty, the map endpoint must return empty layer arrays,
    and must NEVER invent dummy/sample coordinates.
    """
    res = await async_client.get("/api/v1/map-data?layers=shelters&lat=28.61&lng=77.20&radius_km=10")
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    features = payload["data"]["features"]
    # Must not contain dummy hardcoded shelters
    assert len(features) == 0
    assert payload["data"]["layer_summary"]["shelters"] == 0


@pytest.mark.asyncio
async def test_02_authoritative_5_layers_ingestion_and_query(async_client: AsyncClient, test_db: AsyncSession):
    """
    Creates real records in PostgreSQL/PostGIS models for:
    1. Active SOS Beacons
    2. Responders
    3. Community Reports
    4. Official Hazards / Alerts
    5. Relief Shelters
    Verifies that /api/v1/map-data returns valid GeoJSON FeatureCollection for all 5 layers.
    """
    now = utc_now()
    # 1. Active SOS
    sos = SOSSignal(
        id="sos-map-test-01",
        caller_name="Pooja Sharma",
        caller_phone="+919876543210",
        emergency_type="flood_trapped",
        severity="CRITICAL",
        status="TRIGGERED",
        latitude=19.0760,
        longitude=72.8777,
        accuracy_meters=8.5,
        casualties_count=3,
        battery_percent=88,
        city="Mumbai",
        state="Maharashtra",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    # 2. Responder & Assignment
    resp_user = User(
        id="resp-map-user-01",
        email="sdrf_resp01@aegis.gov.in",
        hashed_password="mock",
        full_name="SDRF Unit 4 Commander",
        role="sdrf_officer",
        is_active=True
    )
    test_db.add(resp_user)

    pref = UserPreference(
        id="pref-map-user-01",
        user_id="resp-map-user-01",
        is_responder_opted_in=True,
        is_available=True,
        last_known_lat=19.0800,
        last_known_lng=72.8800,
        last_location_time=now
    )
    test_db.add(pref)

    assign = SOSAssignment(
        id="assign-map-test-01",
        sos_id="sos-map-test-01",
        responder_user_id="resp-map-user-01",
        status="ACTIVE",
        assigned_at=now,
        last_responder_lat=19.0800,
        last_responder_lon=72.8800,
        last_responder_update=now,
        distance_meters=850.0,
        eta_seconds=180
    )
    test_db.add(assign)

    # 3. Community Report
    rep = IncidentReport(
        id="rep-map-test-01",
        title="Severe Waterlogging on S.V. Road",
        description="Waist-deep water blocking emergency vehicles.",
        category="WATERLOGGING",
        hazard_type="FLOOD",
        severity="HIGH",
        status="ACTIVE",
        latitude=19.0700,
        longitude=72.8700,
        verification_status="VERIFIED",
        is_verified=True,
        upvotes=12,
        city="Mumbai",
        state="Maharashtra",
        created_at=now
    )
    test_db.add(rep)

    # 4. Official Hazard Observation
    haz = NormalizedObservation(
        id="haz-map-test-01",
        hazard_type="FLOOD",
        severity="CRITICAL",
        latitude=19.0650,
        longitude=72.8650,
        source_authority="CWC Flood Forecasting Cell",
        location_name="Mithi River Basin",
        state_name="Maharashtra",
        observed_at=now
    )
    test_db.add(haz)

    # 5. Relief Shelter / Safe Zone
    shelter = SafeZone(
        id="shelter-map-test-01",
        name="BKC Disaster Relief & Evacuation Center",
        latitude=19.0600,
        longitude=72.8600,
        city="Mumbai",
        state="Maharashtra",
        capacity=1500,
        is_active=True,
        amenities=["FOOD", "WATER", "MEDICAL_BEDS", "POWER_BACKUP"]
    )
    test_db.add(shelter)

    await test_db.commit()

    # Query all 5 layers in Mumbai sector
    res = await async_client.get("/api/v1/map-data?layers=all&lat=19.0760&lng=72.8777&radius_km=25")
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True

    data = payload["data"]
    assert data["type"] == "FeatureCollection"
    features = data["features"]
    layer_summary = data["layer_summary"]

    assert layer_summary["sos_beacons"] >= 1
    assert layer_summary["responders"] >= 1
    assert layer_summary["reports"] >= 1 or layer_summary["road_hazards"] >= 1
    assert layer_summary["hazards"] >= 1
    assert layer_summary["shelters"] >= 1

    # Verify GeoJSON structure for SOS feature
    sos_feat = next(f for f in features if f["properties"].get("sos_id") == "sos-map-test-01")
    assert sos_feat["geometry"]["type"] == "Point"
    assert sos_feat["geometry"]["coordinates"] == [72.8777, 19.0760]
    assert sos_feat["properties"]["severity"] == "CRITICAL"
    assert sos_feat["properties"]["status"] == "TRIGGERED"
    assert sos_feat["properties"]["casualties_count"] == 3

    # Verify GeoJSON structure for Responder feature
    resp_feat = next(f for f in features if f["properties"].get("responder_id") == "resp-map-user-01")
    assert resp_feat["geometry"]["type"] == "Point"
    assert resp_feat["properties"]["is_live"] is True
    assert resp_feat["properties"]["eta_seconds"] == 180
    assert "SDRF Unit 4" in resp_feat["properties"]["name"]

    # Verify Shelter feature
    sh_feat = next(f for f in features if f["id"] == "shelter_shelter-map-test-01")
    assert sh_feat["properties"]["name"] == "BKC Disaster Relief & Evacuation Center"
    assert sh_feat["properties"]["capacity"] == 1500


@pytest.mark.asyncio
async def test_03_spatial_bounds_and_proximity_filtering(async_client: AsyncClient, test_db: AsyncSession):
    """
    Tests spatial bounding box (bbox) and radial distance filtering.
    Verifies that distant markers (e.g. in Delhi/Chennai) are excluded when querying Mumbai.
    """
    now = utc_now()
    # Add distant SOS in New Delhi
    delhi_sos = SOSSignal(
        id="sos-delhi-distant",
        caller_name="Delhi Citizen",
        caller_phone="+919811111111",
        emergency_type="fire",
        severity="HIGH",
        status="TRIGGERED",
        latitude=28.6139,
        longitude=77.2090,
        city="New Delhi",
        state="Delhi",
        created_at=now
    )
    test_db.add(delhi_sos)
    await test_db.commit()

    # 1. Query Mumbai radius 50km -> Must NOT include Delhi SOS
    res_mumbai = await async_client.get("/api/v1/map-data?layers=sos_beacons&lat=19.0760&lng=72.8777&radius_km=50")
    assert res_mumbai.status_code == 200
    mumbai_feats = res_mumbai.json()["data"]["features"]
    delhi_in_mumbai = [f for f in mumbai_feats if f["properties"].get("sos_id") == "sos-delhi-distant"]
    assert len(delhi_in_mumbai) == 0

    # 2. Query Delhi Bounding Box -> Must include Delhi SOS
    bbox_delhi = "77.0,28.4,77.4,28.8"
    res_delhi = await async_client.get(f"/api/v1/map-data?layers=sos_beacons&bbox={bbox_delhi}")
    assert res_delhi.status_code == 200
    delhi_feats = res_delhi.json()["data"]["features"]
    delhi_matched = [f for f in delhi_feats if f["properties"].get("sos_id") == "sos-delhi-distant"]
    assert len(delhi_matched) == 1


@pytest.mark.asyncio
async def test_04_status_severity_and_clustering(async_client: AsyncClient, test_db: AsyncSession):
    """
    Tests filtering by status and severity, and validates server-side clustering summary.
    """
    now = utc_now()
    # Add a high severity hazard
    haz = NormalizedObservation(
        id="haz-clust-test",
        hazard_type="FLOOD",
        severity="CRITICAL",
        latitude=19.0760,
        longitude=72.8777,
        source_authority="NDMA",
        location_name="Mumbai Central",
        state_name="Maharashtra",
        observed_at=now
    )
    test_db.add(haz)
    await test_db.commit()

    # Severity filter: CRITICAL
    res_crit = await async_client.get("/api/v1/map-data?layers=all&severity=CRITICAL&lat=19.0760&lng=72.8777&radius_km=100")
    assert res_crit.status_code == 200
    crit_feats = res_crit.json()["data"]["features"]
    for f in crit_feats:
        if f["properties"].get("layer") in ["hazards", "reports", "sos_beacons"]:
            assert f["properties"]["severity"] == "CRITICAL"

    # Clustering enabled
    res_clust = await async_client.get("/api/v1/map-data?layers=all&cluster=true&lat=19.0760&lng=72.8777&radius_km=100")
    assert res_clust.status_code == 200
    data = res_clust.json()["data"]
    assert data["clustering"] is not None
    assert data["clustering"]["total_features"] == len(data["features"])
    assert data["clustering"]["cluster_count"] >= 1


@pytest.mark.asyncio
async def test_05_realtime_sos_creation_and_responder_gps_movement(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies full end-to-end operational pipeline:
    1. SOS created via API -> persisted in DB -> appears on map.
    2. Responder assigned.
    3. Responder updates GPS location -> persisted in DB -> marker coordinates update.
    """
    # 1. Create SOS Distress Beacon
    sos_payload = {
        "caller_name": "Kavita Rao",
        "caller_phone": "+919988776655",
        "emergency_type": "building_collapse",
        "severity": "CRITICAL",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy_meters": 5.0,
        "city": "Bengaluru",
        "state": "Karnataka",
        "casualties_count": 2,
        "idempotency_key": "e2e-map-sos-001"
    }
    res_sos = await async_client.post("/api/v1/sos", json=sos_payload)
    assert res_sos.status_code == 200
    sos_id = res_sos.json()["data"]["id"]

    # 2. Check Map Data for Bengaluru
    res_map_sos = await async_client.get(f"/api/v1/map-data?layers=sos_beacons&lat=12.9716&lng=77.5946&radius_km=10")
    assert res_map_sos.status_code == 200
    sos_features = res_map_sos.json()["data"]["features"]
    matched_sos = [f for f in sos_features if f["properties"].get("sos_id") == sos_id]
    assert len(matched_sos) == 1
    assert matched_sos[0]["geometry"]["coordinates"] == [77.5946, 12.9716]

    # 3. Create Responder and Assign
    resp_id = "blr-responder-e2e"
    resp = User(id=resp_id, email="blr_resp@aegis.gov.in", hashed_password="mock", full_name="Bengaluru QRT Unit", role="responder", is_active=True)
    test_db.add(resp)
    assignment = SOSAssignment(
        id="blr-assign-e2e",
        sos_id=sos_id,
        responder_user_id=resp_id,
        status="ACTIVE",
        last_responder_lat=12.9500,
        last_responder_lon=77.5800,
        last_responder_update=utc_now()
    )
    test_db.add(assignment)
    await test_db.commit()

    # 4. Responder submits live GPS movement update
    new_resp_lat = 12.9650
    new_resp_lon = 77.5900
    loc_payload = {
        "latitude": new_resp_lat,
        "longitude": new_resp_lon,
        "accuracy_meters": 4.0,
        "speed_kmh": 42.0
    }
    res_loc = await async_client.post(
        f"/api/v1/sos/{sos_id}/responder-location",
        json=loc_payload,
        headers={"X-Aegis-User-Id": "blr-responder-e2e"}
    )
    assert res_loc.status_code == 200

    # 5. Query Map Data for Responders in Bengaluru -> Must return exact new GPS coordinates
    res_resp_map = await async_client.get(f"/api/v1/map-data?layers=responders&lat=12.9716&lng=77.5946&radius_km=15")
    assert res_resp_map.status_code == 200
    resp_features = res_resp_map.json()["data"]["features"]
    matched_resp = next(f for f in resp_features if f["properties"].get("responder_id") == "blr-responder-e2e")

    assert matched_resp["geometry"]["coordinates"] == [new_resp_lon, new_resp_lat]
    assert matched_resp["properties"]["is_live"] is True
    assert matched_resp["properties"]["sos_id"] == sos_id
    assert matched_resp["properties"]["status"] == "DISPATCHED_EN_ROUTE"
