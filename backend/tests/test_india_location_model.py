"""
Tests for Comprehensive India Location Model covering all 36 States & UTs.
"""
import pytest
from backend.app.providers.adapters.geographic import GeographicLocationProvider, OFFLINE_LOCATIONS, haversine_km


def test_offline_centroids_cover_all_regions():
    assert len(OFFLINE_LOCATIONS) >= 36

    states = {loc["state"] for loc in OFFLINE_LOCATIONS}
    # Check major states & UTs
    assert "Andhra Pradesh" in states
    assert "Telangana" in states
    assert "Karnataka" in states
    assert "Tamil Nadu" in states
    assert "Maharashtra" in states
    assert "Delhi" in states
    assert "Kerala" in states
    assert "Gujarat" in states
    assert "Rajasthan" in states
    assert "Uttar Pradesh" in states
    assert "Bihar" in states
    assert "West Bengal" in states
    assert "Odisha" in states
    assert "Assam" in states
    assert "Punjab" in states
    assert "Haryana" in states
    assert "Madhya Pradesh" in states
    assert "Jharkhand" in states
    assert "Chhattisgarh" in states
    assert "Himachal Pradesh" in states
    assert "Uttarakhand" in states
    assert "Goa" in states
    assert "Tripura" in states
    assert "Meghalaya" in states
    assert "Manipur" in states
    assert "Nagaland" in states
    assert "Mizoram" in states
    assert "Arunachal Pradesh" in states
    assert "Sikkim" in states
    assert "Jammu and Kashmir" in states
    assert "Ladakh" in states
    assert "Chandigarh" in states
    assert "Puducherry" in states
    assert "Andaman and Nicobar Islands" in states
    assert "Dadra and Nagar Haveli and Daman and Diu" in states
    assert "Lakshadweep" in states


def test_reverse_geocoding_accuracy():
    # Mumbai coordinates
    res_mumbai = GeographicLocationProvider.reverse_geocode_offline(19.0760, 72.8777)
    assert res_mumbai["state"] == "Maharashtra"
    assert "Mumbai" in res_mumbai["name"]

    # Bengaluru coordinates
    res_blr = GeographicLocationProvider.reverse_geocode_offline(12.9716, 77.5946)
    assert res_blr["state"] == "Karnataka"
    assert "Bengaluru" in res_blr["name"]

    # Kolkata coordinates
    res_kol = GeographicLocationProvider.reverse_geocode_offline(22.5726, 88.3639)
    assert res_kol["state"] == "West Bengal"
    assert "Kolkata" in res_kol["name"]


def test_haversine_distance():
    # Distance between New Delhi (28.6139, 77.2090) and Gurugram (28.4595, 77.0266) is approx 24-30 km
    dist = haversine_km(28.6139, 77.2090, 28.4595, 77.0266)
    assert 20.0 <= dist <= 35.0