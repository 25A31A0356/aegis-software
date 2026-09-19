/**
 * AEGIS Shared Location Service
 * Centralized location system for Homepage, Analytics, Safety, Reports, Live Map, and Ask AEGIS.
 */

export interface LocationCoordinates {
  latitude: number;
  longitude: number;
}

export interface LocationSearchResult {
  id: string;
  name: string;
  stateName: string;
  district: string;
  stateId: string;
  coordinates: [number, number]; // [lat, lng]
  riskScore: number;
  riskLevel: 'Low' | 'Medium' | 'High' | 'Critical';
  weatherSnippet?: string;
  confidence?: number;
}

export interface GeocodedAddress {
  cityName: string;
  stateName: string;
  district: string;
  stateId: string;
  readableAddress: string;
  coordinates: [number, number];
}

export interface SavedLocationItem {
  id: string;
  name: string;
  category: 'home' | 'work' | 'family' | 'other';
  coordinates: [number, number];
  stateName: string;
  district: string;
  riskScore: number;
  riskLevel: 'Low' | 'Medium' | 'High' | 'Critical';
  weatherSnippet: string;
  isCurrent?: boolean;
}

export interface NearbyActivityItem {
  id: string;
  hazardType: 'Flood' | 'Heavy Rain' | 'Lightning' | 'Cyclone' | 'Fire' | 'Earthquake' | 'Road Blockage' | 'Landslide' | 'Other';
  title: string;
  locationName: string;
  distanceKm: number;
  timestamp: string;
  severity: 'Critical' | 'Warning' | 'Watch' | 'Minor';
  coordinates: [number, number];
  source: string;
  status: string;
  recommendedAction: string;
  safetyGuideSlug?: string;
}

export type GeolocationErrorCode = 'PERMISSION_DENIED' | 'POSITION_UNAVAILABLE' | 'TIMEOUT' | 'NOT_SUPPORTED' | 'UNKNOWN';

export interface GeolocationResult {
  success: boolean;
  coordinates?: [number, number];
  address?: GeocodedAddress;
  error?: {
    code: GeolocationErrorCode;
    message: string;
    friendlyAdvice: string;
  };
}

const STORAGE_KEY = 'aegis_saved_locations_v1';

export const INDIAN_CITIES_REGISTRY: LocationSearchResult[] = [
  { id: 'city-mumbai', name: 'Mumbai', stateName: 'Maharashtra', district: 'Mumbai Suburban', stateId: 'MH', coordinates: [19.0760, 72.8777], riskScore: 78, riskLevel: 'High', weatherSnippet: '31°C • Heavy Showers' },
  { id: 'city-delhi', name: 'New Delhi', stateName: 'Delhi', district: 'New Delhi', stateId: 'DL', coordinates: [28.6139, 77.2090], riskScore: 58, riskLevel: 'Medium', weatherSnippet: '28°C • Overcast' },
  { id: 'city-bengaluru', name: 'Bengaluru', stateName: 'Karnataka', district: 'Bengaluru Urban', stateId: 'KA', coordinates: [12.9716, 77.5946], riskScore: 42, riskLevel: 'Medium', weatherSnippet: '26°C • Partly Cloudy' },
  { id: 'city-chennai', name: 'Chennai', stateName: 'Tamil Nadu', district: 'Chennai', stateId: 'TN', coordinates: [13.0827, 80.2707], riskScore: 82, riskLevel: 'High', weatherSnippet: '32°C • Coastal Winds' },
  { id: 'city-kolkata', name: 'Kolkata', stateName: 'West Bengal', district: 'Kolkata', stateId: 'WB', coordinates: [22.5726, 88.3639], riskScore: 68, riskLevel: 'High', weatherSnippet: '30°C • Thunderstorms' },
  { id: 'city-hyderabad', name: 'Hyderabad', stateName: 'Telangana', district: 'Hyderabad', stateId: 'TS', coordinates: [17.3850, 78.4867], riskScore: 52, riskLevel: 'Medium', weatherSnippet: '29°C • Scattered Showers' },
  { id: 'city-guwahati', name: 'Guwahati', stateName: 'Assam', district: 'Kamrup Metropolitan', stateId: 'AS', coordinates: [26.1445, 91.7362], riskScore: 91, riskLevel: 'Critical', weatherSnippet: '27°C • Flood Advisory' },
  { id: 'city-puri', name: 'Puri', stateName: 'Odisha', district: 'Puri', stateId: 'OD', coordinates: [19.8135, 85.8312], riskScore: 94, riskLevel: 'Critical', weatherSnippet: '29°C • Cyclone Watch' },
  { id: 'city-kochi', name: 'Kochi', stateName: 'Kerala', district: 'Ernakulam', stateId: 'KL', coordinates: [9.9312, 76.2673], riskScore: 48, riskLevel: 'Medium', weatherSnippet: '28°C • Moderate Rain' },
  { id: 'city-jaipur', name: 'Jaipur', stateName: 'Rajasthan', district: 'Jaipur', stateId: 'RJ', coordinates: [26.9124, 75.7873], riskScore: 36, riskLevel: 'Low', weatherSnippet: '33°C • Clear Skies' },
  { id: 'city-shimla', name: 'Shimla', stateName: 'Himachal Pradesh', district: 'Shimla', stateId: 'HP', coordinates: [31.1048, 77.1734], riskScore: 64, riskLevel: 'Medium', weatherSnippet: '18°C • Landslide Warning' },
  { id: 'city-patna', name: 'Patna', stateName: 'Bihar', district: 'Patna', stateId: 'BR', coordinates: [25.5941, 85.1376], riskScore: 72, riskLevel: 'High', weatherSnippet: '31°C • River Flood Watch' },
  { id: 'city-dehradun', name: 'Dehradun', stateName: 'Uttarakhand', district: 'Dehradun', stateId: 'UK', coordinates: [30.3165, 78.0322], riskScore: 70, riskLevel: 'High', weatherSnippet: '24°C • Heavy Downpours' },
];

const DEFAULT_SAVED_LOCATIONS: SavedLocationItem[] = [
  {
    id: 'loc-1',
    name: 'Home (Mumbai Suburban)',
    category: 'home',
    coordinates: [19.0760, 72.8777],
    stateName: 'Maharashtra',
    district: 'Mumbai Suburban',
    riskScore: 78,
    riskLevel: 'High',
    weatherSnippet: '31°C • Heavy Showers',
  },
  {
    id: 'loc-2',
    name: 'Office (Bandra-Kurla Complex)',
    category: 'work',
    coordinates: [19.0596, 72.8656],
    stateName: 'Maharashtra',
    district: 'Mumbai City',
    riskScore: 65,
    riskLevel: 'Medium',
    weatherSnippet: '30°C • Thunderstorms',
  },
  {
    id: 'loc-3',
    name: 'Parents (Pune Kothrud)',
    category: 'family',
    coordinates: [18.5074, 73.8077],
    stateName: 'Maharashtra',
    district: 'Pune',
    riskScore: 28,
    riskLevel: 'Low',
    weatherSnippet: '27°C • Overcast',
  },
  {
    id: 'loc-4',
    name: 'Coastal Site (Puri Beach)',
    category: 'other',
    coordinates: [19.8135, 85.8312],
    stateName: 'Odisha',
    district: 'Puri',
    riskScore: 92,
    riskLevel: 'Critical',
    weatherSnippet: '29°C • Cyclone Watch',
  },
];

class LocationServiceClass {
  private savedLocations: SavedLocationItem[] = [];
  private selectedLocation: LocationSearchResult = INDIAN_CITIES_REGISTRY[0]; // Mumbai default

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage() {
    try {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('agies_saved_locations_v1');
        if (stored) {
          this.savedLocations = JSON.parse(stored);
        } else {
          this.savedLocations = DEFAULT_SAVED_LOCATIONS;
          this.saveToStorage();
        }
      } else {
        this.savedLocations = DEFAULT_SAVED_LOCATIONS;
      }
    } catch (e) {
      console.warn('[LocationService] Failed loading from storage:', e);
      this.savedLocations = DEFAULT_SAVED_LOCATIONS;
    }
  }

  private saveToStorage() {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.savedLocations));
      }
    } catch (e) {
      console.warn('[LocationService] Failed saving to storage:', e);
    }
  }

  /**
   * 1. getCurrentLocation()
   * Requests browser geolocation permission and handles permission denied, timeout, unavailable states.
   */
  async getCurrentLocation(): Promise<GeolocationResult> {
    if (typeof window === 'undefined' || !navigator.geolocation) {
      return {
        success: false,
        error: {
          code: 'NOT_SUPPORTED',
          message: 'Geolocation is not supported by your browser.',
          friendlyAdvice: 'Please use the search bar above to manually select your city or area.',
        },
      };
    }

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          const address = await this.reverseGeocode(lat, lng);
          
          resolve({
            success: true,
            coordinates: [lat, lng],
            address,
          });
        },
        (error) => {
          let code: GeolocationErrorCode = 'UNKNOWN';
          let message = 'Unable to determine your GPS location.';
          let friendlyAdvice = 'You can still enter your city or district in the search bar.';

          switch (error.code) {
            case error.PERMISSION_DENIED:
              code = 'PERMISSION_DENIED';
              message = 'Location access was denied.';
              friendlyAdvice = 'Please enable location permissions in your browser settings, or use manual city search.';
              break;
            case error.POSITION_UNAVAILABLE:
              code = 'POSITION_UNAVAILABLE';
              message = 'GPS signal is currently unavailable.';
              friendlyAdvice = 'Check your network connection or select a station from the list.';
              break;
            case error.TIMEOUT:
              code = 'TIMEOUT';
              message = 'Location request timed out.';
              friendlyAdvice = 'Please try again or select your location manually.';
              break;
          }

          resolve({
            success: false,
            error: { code, message, friendlyAdvice },
          });
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000,
        }
      );
    });
  }

  /**
   * 2. searchLocation(query)
   * Searches registry and geocoding index with error and empty state handling
   */
  async searchLocation(query: string): Promise<LocationSearchResult[]> {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return [];

    // Filter registry
    const matches = INDIAN_CITIES_REGISTRY.filter((city) => {
      return (
        city.name.toLowerCase().includes(trimmed) ||
        city.stateName.toLowerCase().includes(trimmed) ||
        city.district.toLowerCase().includes(trimmed) ||
        city.stateId.toLowerCase().includes(trimmed)
      );
    });

    if (matches.length > 0) {
      return matches;
    }

    // Check for coordinate search (e.g. "19.07, 72.87")
    const coordMatch = trimmed.match(/^([0-9.-]+)[,\s]+([0-9.-]+)$/);
    if (coordMatch) {
      const lat = parseFloat(coordMatch[1]);
      const lng = parseFloat(coordMatch[2]);
      if (!isNaN(lat) && !isNaN(lng) && lat >= 6 && lat <= 38 && lng >= 68 && lng <= 98) {
        const address = await this.reverseGeocode(lat, lng);
        return [
          {
            id: `coord-${lat.toFixed(2)}-${lng.toFixed(2)}`,
            name: address.cityName,
            stateName: address.stateName,
            district: address.district,
            stateId: address.stateId,
            coordinates: [lat, lng],
            riskScore: 60,
            riskLevel: 'Medium',
            weatherSnippet: '29°C • Telemetry Active',
          },
        ];
      }
    }

    return [];
  }

  /**
   * 3. reverseGeocode(lat, lng)
   * Reverse geocodes coordinates to readable city and district
   */
  async reverseGeocode(lat: number, lng: number): Promise<GeocodedAddress> {
    // Find closest registered Indian city
    let closestCity = INDIAN_CITIES_REGISTRY[0];
    let minDistance = Infinity;

    for (const city of INDIAN_CITIES_REGISTRY) {
      const dist = this.calculateDistanceKm([lat, lng], city.coordinates);
      if (dist < minDistance) {
        minDistance = dist;
        closestCity = city;
      }
    }

    // If within 45 km, use specific district info
    if (minDistance <= 45) {
      return {
        cityName: closestCity.name,
        stateName: closestCity.stateName,
        district: closestCity.district,
        stateId: closestCity.stateId,
        readableAddress: `${closestCity.name}, ${closestCity.district}, ${closestCity.stateName}`,
        coordinates: [lat, lng],
      };
    }

    return {
      cityName: `${closestCity.name} Sector`,
      stateName: closestCity.stateName,
      district: closestCity.district,
      stateId: closestCity.stateId,
      readableAddress: `Near ${closestCity.name} (${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E), ${closestCity.stateName}`,
      coordinates: [lat, lng],
    };
  }

  /**
   * 4. saveLocation(location)
   */
  saveLocation(location: Omit<SavedLocationItem, 'id'>): SavedLocationItem[] {
    const newItem: SavedLocationItem = {
      ...location,
      id: `loc-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
    };
    this.savedLocations.unshift(newItem);
    this.saveToStorage();
    return this.getSavedLocations();
  }

  /**
   * 5. removeLocation(id)
   */
  removeLocation(id: string): SavedLocationItem[] {
    this.savedLocations = this.savedLocations.filter((item) => item.id !== id);
    this.saveToStorage();
    return this.getSavedLocations();
  }

  /**
   * 6. selectLocation(locationOrId)
   */
  selectLocation(target: LocationSearchResult | SavedLocationItem | string): LocationSearchResult {
    if (typeof target === 'string') {
      const match =
        INDIAN_CITIES_REGISTRY.find((c) => c.id === target || c.name.toLowerCase() === target.toLowerCase()) ||
        this.savedLocations.find((l) => l.id === target);
      if (match) {
        this.selectedLocation = {
          id: match.id,
          name: match.name,
          stateName: match.stateName,
          district: match.district,
          stateId: (match as any).stateId || 'IN',
          coordinates: match.coordinates,
          riskScore: match.riskScore,
          riskLevel: match.riskLevel,
          weatherSnippet: match.weatherSnippet,
        };
      }
    } else {
      this.selectedLocation = {
        id: target.id,
        name: target.name,
        stateName: target.stateName,
        district: target.district,
        stateId: (target as any).stateId || 'IN',
        coordinates: target.coordinates,
        riskScore: target.riskScore,
        riskLevel: target.riskLevel,
        weatherSnippet: target.weatherSnippet,
      };
    }
    return this.selectedLocation;
  }

  getSelectedLocation(): LocationSearchResult {
    return this.selectedLocation;
  }

  getSavedLocations(): SavedLocationItem[] {
    return [...this.savedLocations];
  }

  calculateDistanceKm(coords1: [number, number], coords2: [number, number]): number {
    const [lat1, lon1] = coords1;
    const [lat2, lon2] = coords2;
    const R = 6371;
    const dLat = (lat2 - lat1) * (Math.PI / 180);
    const dLon = (lon2 - lon1) * (Math.PI / 180);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * (Math.PI / 180)) *
        Math.cos(lat2 * (Math.PI / 180)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c * 10) / 10;
  }

  getNearbyActivity(center: [number, number]): NearbyActivityItem[] {
    const [cLat, cLng] = center;

    return [
      {
        id: 'act-1',
        hazardType: 'Heavy Rain',
        title: 'Intense Convective Cloudburst & Waterlogging',
        locationName: 'Subway & Lowland Sector (East)',
        distanceKm: this.calculateDistanceKm(center, [cLat + 0.04, cLng + 0.03]),
        timestamp: '4 mins ago',
        severity: 'Critical',
        coordinates: [cLat + 0.04, cLng + 0.03],
        source: 'IMD Doppler Radar DWR-04',
        status: 'Active Red Alert',
        recommendedAction: 'Avoid low-lying subways. Do not drive through standing water.',
        safetyGuideSlug: 'floods',
      },
      {
        id: 'act-2',
        hazardType: 'Lightning',
        title: 'Multiple Cloud-to-Ground Lightning Strikes',
        locationName: 'North Ridge & Industrial Belt',
        distanceKm: this.calculateDistanceKm(center, [cLat + 0.075, cLng + 0.055]),
        timestamp: '12 mins ago',
        severity: 'Warning',
        coordinates: [cLat + 0.075, cLng + 0.055],
        source: 'Ground Electrostatic Sensor Array',
        status: 'Severe Activity',
        recommendedAction: 'Stay indoors away from open fields, high trees, and metal towers.',
        safetyGuideSlug: 'floods',
      },
      {
        id: 'act-3',
        hazardType: 'Road Blockage',
        title: 'Tree Fall & Power Cable Snapping',
        locationName: 'Main Arterial Highway (KM 14)',
        distanceKm: this.calculateDistanceKm(center, [cLat - 0.03, cLng + 0.02]),
        timestamp: '25 mins ago',
        severity: 'Warning',
        coordinates: [cLat - 0.03, cLng + 0.02],
        source: 'Traffic Command & Citizen Report #482',
        status: 'Traffic Diverted',
        recommendedAction: 'Use Western Bypass diversion route.',
        safetyGuideSlug: 'cyclones',
      },
      {
        id: 'act-4',
        hazardType: 'Flood',
        title: 'River Basin Riverbank Crest Level Rising',
        locationName: 'Downstream Catchment Zone',
        distanceKm: this.calculateDistanceKm(center, [cLat + 0.09, cLng - 0.05]),
        timestamp: '42 mins ago',
        severity: 'Critical',
        coordinates: [cLat + 0.09, cLng - 0.05],
        source: 'Central Water Commission (CWC)',
        status: 'Breach Watch',
        recommendedAction: 'Evacuate riverbank settlements to designated safe shelters.',
        safetyGuideSlug: 'floods',
      },
      {
        id: 'act-5',
        hazardType: 'Cyclone',
        title: 'Squally Gale Winds (75-85 km/h gusts)',
        locationName: 'Coastal Embankment Sector',
        distanceKm: this.calculateDistanceKm(center, [cLat - 0.08, cLng - 0.07]),
        timestamp: '1 hr ago',
        severity: 'Critical',
        coordinates: [cLat - 0.08, cLng - 0.07],
        source: 'IMD Coastal Telemetry',
        status: 'Cyclone Warning',
        recommendedAction: 'Secure roof sheets. Fishermen warned against deep sea venture.',
        safetyGuideSlug: 'cyclones',
      },
    ];
  }
}

export const LocationService = new LocationServiceClass();
