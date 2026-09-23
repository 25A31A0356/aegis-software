"""
AEGIS UNIFIED DATA CORE - Real Community Reporting & Operator Verification Integration Suite
Tests the complete production community reporting lifecycle:
1. Multi-Category Submission (Flood, Fire, Road Blocked, Landslide, Building Damage, Waterlogging, Power Failure, Missing Person, Other)
2. Photo & Video Media Uploads with MIME and size verification
3. Operator Verification & Dynamic Severity Modification
4. Operator Rejection with Mandatory Reason
5. Cross-Linking of Community Reports to Active SOS Distress Beacons & Incidents
6. Strict Taxonomy Separation: COMMUNITY_REPORT vs OFFICIAL_ALERT
7. Spatial Bounds & Category Filtering
"""
import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from backend.app.database.models import (
    IncidentReport, SOSSignal, AlertRecord, User, utc_now
)


@pytest.mark.asyncio
async def test_01_submit_community_report_all_categories(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies citizen submissions across all 9 supported emergency categories:
    Flood, Fire, Road Blocked, Landslide, Building Damage, Waterlogging, Power Failure, Missing Person, Other.
    Confirms initial state is SUBMITTED with verification_status: UNVERIFIED.
    """
    categories = [
        ("FLOOD", "Flood", "Severe flash flooding in lower valley"),
        ("FIRE", "Fire", "Commercial warehouse fire spreading to nearby structures"),
        ("ROAD_BLOCKED", "Road Blocked", "Fallen electrical pole blocking main avenue"),
        ("LANDSLIDE", "Landslide", "Mud and boulders blocking mountain pass"),
        ("BUILDING_DAMAGE", "Building Damage", "Cracked load-bearing columns after tremor"),
        ("WATERLOGGING", "Waterlogging", "3 feet waterlogging at railway underpass"),
        ("POWER_FAILURE", "Power Failure", "Grid transformer explosion causing blackout"),
        ("MISSING_PERSON", "Missing Person", "Elderly citizen separated during evacuation"),
        ("OTHER", "Other", "Hazardous chemical leakage in industrial corridor")
    ]

    for cat_code, cat_label, description in categories:
        payload = {
            "category": cat_code,
            "title": f"Ground-truth Report: {cat_label}",
            "description": description,
            "severity": "HIGH",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "accuracy_meters": 8.0,
            "city": "Mumbai",
            "state": "Maharashtra",
            "reporter_name": "Citizen Reporter",
            "idempotency_key": f"test-cat-report-{cat_code.lower()}"
        }

        res = await async_client.post("/api/v1/reports", json=payload)
        assert res.status_code == 200, f"Failed for category {cat_code}: {res.text}"
        data = res.json()["data"]

        assert data["category"] == cat_code
        assert data["status"] == "SUBMITTED"
        assert data["verification_status"] == "UNVERIFIED"
        assert data["is_verified"] is False
        assert data["source_type"] == "COMMUNITY_REPORT"
        assert "Unverified" in data["provenance_label"]


@pytest.mark.asyncio
async def test_02_media_upload_photo_and_video(async_client: AsyncClient):
    """
    Verifies secure media upload vault for photos (PNG/JPEG) and video clips (MP4).
    """
    # 1. Upload Photo
    fake_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    photo_file = ("damage_photo.png", io.BytesIO(fake_png_bytes), "image/png")

    res_photo = await async_client.post(
        "/api/v1/reports/upload-media",
        files={"file": photo_file}
    )
    assert res_photo.status_code == 200
    photo_data = res_photo.json()["data"]
    assert photo_data["media_type"] == "PHOTO"
    assert photo_data["url"].startswith("/static/uploads/")
    assert photo_data["size_bytes"] == len(fake_png_bytes)

    # 2. Upload Video
    fake_mp4_bytes = b"\x00\x00\x00 ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free"
    video_file = ("flood_stream.mp4", io.BytesIO(fake_mp4_bytes), "video/mp4")

    res_video = await async_client.post(
        "/api/v1/reports/upload-media",
        files={"file": video_file}
    )
    assert res_video.status_code == 200
    video_data = res_video.json()["data"]
    assert video_data["media_type"] == "VIDEO"
    assert video_data["url"].startswith("/static/uploads/")
    assert video_data["url"].endswith(".mp4")


@pytest.mark.asyncio
async def test_03_operator_verify_report_and_severity_update(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that a Web Operator can review an unverified report,
    elevate it to VERIFIED, adjust the severity to CRITICAL, and attach operator audit notes.
    """
    # Create initial report
    create_payload = {
        "category": "LANDSLIDE",
        "title": "National Highway blocked by landslide debris",
        "description": "Massive landslide blocking both lanes of NH-44.",
        "severity": "MODERATE",
        "latitude": 32.2226,
        "longitude": 75.6421,
        "city": "Pathankot",
        "state": "Punjab"
    }
    res_create = await async_client.post("/api/v1/reports", json=create_payload)
    assert res_create.status_code == 200
    report_id = res_create.json()["data"]["id"]

    # Operator verifies report and upgrades severity to CRITICAL
    operator_id = "sdrf-controller-01"
    verify_payload = {
        "severity": "CRITICAL",
        "operator_notes": "Confirmed with local police station dispatch."
    }
    res_verify = await async_client.post(
        f"/api/v1/reports/{report_id}/verify",
        json=verify_payload,
        headers={"X-Aegis-User-Id": operator_id}
    )
    assert res_verify.status_code == 200
    verified_data = res_verify.json()["data"]

    assert verified_data["status"] == "VERIFIED"
    assert verified_data["verification_status"] == "VERIFIED"
    assert verified_data["is_verified"] is True
    assert verified_data["severity"] == "CRITICAL"
    assert verified_data["verified_by_user_id"] == operator_id
    assert verified_data["verified_at"] is not None
    assert "Verified" in verified_data["provenance_label"]


@pytest.mark.asyncio
async def test_04_operator_reject_report_with_reason(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that a Web Operator can reject an unsubstantiated report with a mandatory rejection reason.
    """
    create_payload = {
        "category": "FIRE",
        "title": "Unconfirmed smoke sighting",
        "description": "Saw white smoke near forest edge.",
        "severity": "LOW",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "city": "Chennai",
        "state": "Tamil Nadu"
    }
    res_create = await async_client.post("/api/v1/reports", json=create_payload)
    assert res_create.status_code == 200
    report_id = res_create.json()["data"]["id"]

    # Operator rejects report
    operator_id = "control-room-officer"
    reject_payload = {
        "rejection_reason": "Forest department confirmed controlled agricultural burn. No emergency.",
        "operator_notes": "Checked satellite thermal feeds. Zero wildfire anomaly."
    }
    res_reject = await async_client.post(
        f"/api/v1/reports/{report_id}/reject",
        json=reject_payload,
        headers={"X-Aegis-User-Id": operator_id}
    )
    assert res_reject.status_code == 200
    rejected_data = res_reject.json()["data"]

    assert rejected_data["status"] == "REJECTED"
    assert rejected_data["verification_status"] == "REJECTED"
    assert rejected_data["is_verified"] is False
    assert "agricultural burn" in rejected_data["rejection_reason"]


@pytest.mark.asyncio
async def test_05_link_report_to_sos_and_incident(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies cross-linking a community report to an active citizen SOS distress beacon and master incident.
    """
    now = utc_now()
    # 1. Create active SOS
    sos = SOSSignal(
        id="sos-linked-beacon-01",
        caller_name="Trapped Family",
        caller_phone="+919876543210",
        emergency_type="flood_trapped",
        severity="CRITICAL",
        status="RESPONDER_EN_ROUTE",
        latitude=28.6139,
        longitude=77.2090,
        city="New Delhi",
        state="Delhi",
        created_at=now,
        last_location_update=now
    )
    test_db.add(sos)

    # 2. Create community report
    report = IncidentReport(
        id="report-linked-01",
        category="WATERLOGGING",
        hazard_type="WATERLOGGING",
        title="Severe waterlogging near metro station",
        description="Vehicles submerged under metro flyover.",
        severity="HIGH",
        status="SUBMITTED",
        verification_status="UNVERIFIED",
        latitude=28.6140,
        longitude=77.2095,
        created_at=now
    )
    test_db.add(report)
    await test_db.commit()

    # 3. Operator links report to SOS beacon
    link_payload = {
        "linked_sos_id": "sos-linked-beacon-01",
        "linked_incident_id": "INC-DELHI-MONSOON-2026",
        "operator_notes": "Ground photo confirms depth matches distress beacon SOS."
    }
    res_link = await async_client.post(
        f"/api/v1/reports/report-linked-01/link",
        json=link_payload,
        headers={"X-Aegis-User-Id": "incident-commander"}
    )
    assert res_link.status_code == 200
    linked_data = res_link.json()["data"]

    assert linked_data["linked_sos_id"] == "sos-linked-beacon-01"
    assert linked_data["linked_incident_id"] == "INC-DELHI-MONSOON-2026"
    assert "Ground photo" in linked_data["operator_notes"]


@pytest.mark.asyncio
async def test_06_strict_taxonomy_distinction_from_official_alerts(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies that community reports are strictly classified as source_type='COMMUNITY_REPORT'
    and are never returned as OFFICIAL_ALERT.
    """
    now = utc_now()
    # Official Alert
    alert = AlertRecord(
        id="alert-imd-official-01",
        alert_code="IMD-RED-MUMBAI-2026",
        hazard_type="CYCLONE",
        severity="critical",
        status="active",
        headline="IMD Red Alert: Cyclone Approaching Konkan Coast",
        description="Extremely severe cyclonic storm approaching coastline.",
        state_name="Maharashtra",
        district_name="Mumbai",
        latitude=18.9220,
        longitude=72.8347,
        source_agency="India Meteorological Department (IMD)",
        provenance_type="official_warning",
        published_at=now
    )
    test_db.add(alert)

    # Community Report (even if verified)
    report = IncidentReport(
        id="report-comm-tax-01",
        category="CYCLONE",
        hazard_type="CYCLONE",
        title="High sea waves crashing over promenade",
        description="Marine drive promenade closed due to tidal surge.",
        severity="HIGH",
        status="VERIFIED",
        verification_status="VERIFIED",
        is_verified=True,
        source_type="COMMUNITY_REPORT",
        latitude=18.9400,
        longitude=72.8200,
        created_at=now
    )
    test_db.add(report)
    await test_db.commit()

    # Query reports endpoint
    res_reports = await async_client.get("/api/v1/reports?category=CYCLONE")
    assert res_reports.status_code == 200
    reports_list = res_reports.json()["data"]
    for r in reports_list:
        assert r["source_type"] == "COMMUNITY_REPORT"
        assert r["source"] == "COMMUNITY"
        assert "Alert" not in r["source_type"]

    # Query alerts endpoint
    res_alerts = await async_client.get("/api/v1/alerts")
    assert res_alerts.status_code == 200
    alerts_list = res_alerts.json()["data"]
    for a in alerts_list:
        assert a.get("provenance_type") in ["official_warning", "OFFICIAL_ALERT"]
        source_info = a.get("source", {})
        agency = source_info.get("agency", "")
        assert "IMD" in agency or "CWC" in agency or "NDMA" in agency


@pytest.mark.asyncio
async def test_07_spatial_and_category_filtering(async_client: AsyncClient, test_db: AsyncSession):
    """
    Verifies radial spatial distance and category queries for community reports.
    """
    now = utc_now()
    # Bengaluru Waterlogging Report
    rep_blr = IncidentReport(
        id="rep-blr-01",
        category="WATERLOGGING",
        hazard_type="WATERLOGGING",
        title="Silk Board Junction Waterlogging",
        description="Heavy waterlogging causing 4 km traffic tailback.",
        severity="HIGH",
        status="SUBMITTED",
        latitude=12.9176,
        longitude=77.6238,
        city="Bengaluru",
        state="Karnataka",
        created_at=now
    )
    # Delhi Power Failure Report
    rep_delhi = IncidentReport(
        id="rep-delhi-01",
        category="POWER_FAILURE",
        hazard_type="POWER_FAILURE",
        title="South Delhi Feeder Tripped",
        description="Power blackout across 3 sectors.",
        severity="MODERATE",
        status="SUBMITTED",
        latitude=28.5355,
        longitude=77.2410,
        city="New Delhi",
        state="Delhi",
        created_at=now
    )
    test_db.add_all([rep_blr, rep_delhi])
    await test_db.commit()

    # 1. Query within 25km of Bengaluru -> Must return Bengaluru report, exclude Delhi
    res_blr = await async_client.get("/api/v1/reports?lat=12.9176&lng=77.6238&radius_km=25")
    assert res_blr.status_code == 200
    blr_items = res_blr.json()["data"]
    assert any(r["id"] == "rep-blr-01" for r in blr_items)
    assert not any(r["id"] == "rep-delhi-01" for r in blr_items)

    # 2. Query Category POWER_FAILURE
    res_cat = await async_client.get("/api/v1/reports?category=POWER_FAILURE")
    assert res_cat.status_code == 200
    cat_items = res_cat.json()["data"]
    assert any(r["id"] == "rep-delhi-01" for r in cat_items)
    assert not any(r["id"] == "rep-blr-01" for r in cat_items)
