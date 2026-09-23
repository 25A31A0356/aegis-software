"""
Tests for Comprehensive Pan-India 780+ Districts Location Model & Spatial Registry.
Covers all 28 States and 8 Union Territories.
"""
import pytest
from backend.app.providers.adapters.geographic import GeographicLocationProvider, OFFLINE_LOCATIONS, haversine_km
from backend.app.providers.adapters.india_districts_data import ALL_INDIA_DISTRICTS


def test_pan_india_districts_count_and_coverage():
    """Verify that spatial registry contains over 780 official districts."""
    assert len(ALL_INDIA_DISTRICTS) >= 780
    assert len(OFFLINE_LOCATIONS) >= 780

    states = {loc["state"] for loc in ALL_INDIA_DISTRICTS}
    # All 28 Indian States
    expected_states = [
        "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
        "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
        "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
        "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
        "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"
    ]
    for st in expected_states:
        assert st in states, f"Missing State: {st}"

    # All 8 Union Territories
    expected_uts = [
        "Andaman and Nicobar Islands", "Chandigarh",
        "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
        "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
    ]
    for ut in expected_uts:
        assert ut in states, f"Missing Union Territory: {ut}"


def test_reverse_geocoding_accuracy_across_cardinal_corners():
    """Authoritatively test reverse-geocoding across India's North, South, East, West, and Island territories."""
    # 1. North: Leh, Ladakh
    res_leh = GeographicLocationProvider.reverse_geocode_offline(34.1526, 77.5771)
    assert res_leh["state"] == "Ladakh"
    assert "Leh" in res_leh["district"] or "Leh" in res_leh["name"]
    assert res_leh["country"] == "India"
    assert res_leh["elevation"] >= 3000

    # 2. South: Kanniyakumari, Tamil Nadu
    res_kanyakumari = GeographicLocationProvider.reverse_geocode_offline(8.0883, 77.5385)
    assert res_kanyakumari["state"] == "Tamil Nadu"
    assert "Kanniyakumari" in res_kanyakumari["district"] or "Kanyakumari" in res_kanyakumari["district"]

    # 3. East: Anjaw / Tezu, Arunachal Pradesh
    res_east = GeographicLocationProvider.reverse_geocode_offline(28.0000, 96.5000)
    assert res_east["state"] == "Arunachal Pradesh"
    assert "Anjaw" in res_east["district"]

    # 4. West: Kachchh, Gujarat
    res_west = GeographicLocationProvider.reverse_geocode_offline(23.2420, 69.6669)
    assert res_west["state"] == "Gujarat"
    assert "Kachchh" in res_west["district"] or "Kutch" in res_west["district"]

    # 5. Island UT 1: Port Blair, Andaman & Nicobar
    res_andaman = GeographicLocationProvider.reverse_geocode_offline(11.6234, 92.7265)
    assert res_andaman["state"] == "Andaman and Nicobar Islands"
    assert "Andaman" in res_andaman["district"]

    # 6. Island UT 2: Kavaratti, Lakshadweep
    res_lak = GeographicLocationProvider.reverse_geocode_offline(10.5669, 72.6420)
    assert res_lak["state"] == "Lakshadweep"
    assert "Lakshadweep" in res_lak["district"]

    # 7. Major Metros
    res_mumbai = GeographicLocationProvider.reverse_geocode_offline(19.0760, 72.8777)
    assert res_mumbai["state"] == "Maharashtra"

    res_delhi = GeographicLocationProvider.reverse_geocode_offline(28.6139, 77.2090)
    assert res_delhi["state"] == "Delhi"

    res_blr = GeographicLocationProvider.reverse_geocode_offline(12.9716, 77.5946)
    assert res_blr["state"] == "Karnataka"


def test_haversine_distance():
    # Distance between New Delhi (28.6139, 77.2090) and Gurugram (28.4595, 77.0266) is approx 24-30 km
    dist = haversine_km(28.6139, 77.2090, 28.4595, 77.0266)
    assert 20.0 <= dist <= 35.0