import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { DEMO_STATES } from '../data/demoStates';
import { DEMO_CITY_WEATHER } from '../data/demoWeather';
import { StateRiskData } from '../types/location';
import { WeatherTelemetry } from '../types/weather';
import { WeatherService, CITY_COORDINATES } from '../services/weatherService';
import {
  LocationService,
  LocationSearchResult,
  SavedLocationItem,
  GeolocationResult,
  INDIAN_CITIES_REGISTRY,
} from '../services/locationService';
import { ProviderRegistry } from '../providers/ProviderRegistry';

export interface LocationErrorState {
  code: string;
  message: string;
  friendlyAdvice: string;
}

interface LocationContextType {
  // Global Synchronized Location State
  selectedLocation: LocationSearchResult;
  selectedCityKey: string;
  weather: WeatherTelemetry;
  selectedState: StateRiskData | undefined;
  statesList: StateRiskData[];
  savedLocations: SavedLocationItem[];
  userCoordinates: [number, number] | null;
  isGpsActive: boolean;
  isLoadingLocation: boolean;
  locationError: LocationErrorState | null;

  // Actions
  clearLocationError: () => void;
  requestCurrentGPS: () => Promise<boolean>;
  searchAndSelectLocation: (query: string) => Promise<LocationSearchResult[]>;
  selectLocationItem: (target: LocationSearchResult | SavedLocationItem | string) => void;
  saveLocationItem: (location: Omit<SavedLocationItem, 'id'>) => void;
  removeLocationItem: (id: string) => void;

  // Backward compatibility helpers
  setSelectedCity: (cityKey: string) => void;
  setSelectedStateById: (stateId: string) => void;
  detectCurrentLocation: () => void;
  resetToNational: () => void;
  isNationalOverview: boolean;
  isLoadingWeather: boolean;
}

const LocationContext = createContext<LocationContextType | undefined>(undefined);

export const LocationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedLocation, setSelectedLocation] = useState<LocationSearchResult>(() =>
    LocationService.getSelectedLocation()
  );
  const [savedLocations, setSavedLocations] = useState<SavedLocationItem[]>(() =>
    LocationService.getSavedLocations()
  );
  const [selectedCityKey, setSelectedCityKey] = useState<string>('mumbai');
  const [selectedStateId, setSelectedStateId] = useState<string | null>('MH');
  const [userCoordinates, setUserCoordinates] = useState<[number, number] | null>(null);
  const [isGpsActive, setIsGpsActive] = useState<boolean>(false);
  const [isNationalOverview, setIsNationalOverview] = useState<boolean>(false);

  const [weather, setWeather] = useState<WeatherTelemetry>(
    () => DEMO_CITY_WEATHER['mumbai'] || DEMO_CITY_WEATHER['hyderabad']
  );
  const [isLoadingLocation, setIsLoadingLocation] = useState<boolean>(false);
  const [isLoadingWeather, setIsLoadingWeather] = useState<boolean>(false);
  const [locationError, setLocationError] = useState<LocationErrorState | null>(null);

  const selectedState = DEMO_STATES.find((s) => s.id === selectedStateId);

  const clearLocationError = useCallback(() => {
    setLocationError(null);
  }, []);

  /**
   * Synchronize Weather & State telemetry for any coordinate pair
   */
  const syncLocationTelemetry = useCallback(
    async (coords: [number, number], cityName: string, stateIdHint?: string) => {
      setIsLoadingWeather(true);
      try {
        const weatherProvider = ProviderRegistry.getWeatherProvider();
        const result = await weatherProvider.getWeatherByCoordinates(coords[0], coords[1]);
        if (result && result.data) {
          setWeather(result.data);
        } else {
          // Fallback to closest demo city
          const cityKey = cityName.toLowerCase().split(' ')[0];
          const demo = DEMO_CITY_WEATHER[cityKey] || DEMO_CITY_WEATHER['mumbai'];
          setWeather({ ...demo, cityName, coordinates: coords });
        }
      } catch (e) {
        console.warn('[LocationContext] Weather provider sync error:', e);
      } finally {
        setIsLoadingWeather(false);
      }

      // Update state ID
      if (stateIdHint) {
        setSelectedStateId(stateIdHint);
      } else {
        const matchState = DEMO_STATES.find((s) =>
          s.name.toLowerCase().includes(cityName.toLowerCase()) ||
          s.capital.toLowerCase().includes(cityName.toLowerCase())
        );
        if (matchState) setSelectedStateId(matchState.id);
      }
    },
    []
  );

  /**
   * Request Current GPS location with friendly error state handling
   */
  const requestCurrentGPS = useCallback(async (): Promise<boolean> => {
    setIsLoadingLocation(true);
    setLocationError(null);

    const result: GeolocationResult = await LocationService.getCurrentLocation();
    setIsLoadingLocation(false);

    if (result.success && result.coordinates && result.address) {
      const coords = result.coordinates;
      setUserCoordinates(coords);
      setIsGpsActive(true);

      const locResult: LocationSearchResult = {
        id: 'user-current-gps',
        name: result.address.cityName,
        stateName: result.address.stateName,
        district: result.address.district,
        stateId: result.address.stateId,
        coordinates: coords,
        riskScore: 74,
        riskLevel: 'High',
        weatherSnippet: 'Live GPS Telemetry Active',
      };

      setSelectedLocation(locResult);
      LocationService.selectLocation(locResult);
      await syncLocationTelemetry(coords, result.address.cityName, result.address.stateId);
      return true;
    } else if (result.error) {
      setLocationError(result.error);
      return false;
    }
    return false;
  }, [syncLocationTelemetry]);

  /**
   * Search for locations and select top match if unambiguous
   */
  const searchAndSelectLocation = useCallback(
    async (query: string): Promise<LocationSearchResult[]> => {
      setIsLoadingLocation(true);
      setLocationError(null);
      try {
        const results = await LocationService.searchLocation(query);
        setIsLoadingLocation(false);

        if (results.length === 0) {
          setLocationError({
            code: 'NOT_FOUND',
            message: `No weather or risk stations found matching "${query}".`,
            friendlyAdvice: 'Try searching by major city (e.g. Mumbai, Delhi, Bengaluru, Chennai) or state.',
          });
        }
        return results;
      } catch (err) {
        setIsLoadingLocation(false);
        setLocationError({
          code: 'SEARCH_FAILED',
          message: 'Location search encountered an error.',
          friendlyAdvice: 'Please check your connection and try again.',
        });
        return [];
      }
    },
    []
  );

  /**
   * Select a location item directly (from saved locations, search results, or map pins)
   */
  const selectLocationItem = useCallback(
    (target: LocationSearchResult | SavedLocationItem | string) => {
      const selected = LocationService.selectLocation(target);
      setSelectedLocation(selected);
      setIsGpsActive(false);
      setIsNationalOverview(false);
      setLocationError(null);

      const cityKey = selected.name.toLowerCase().split(' ')[0];
      setSelectedCityKey(cityKey);
      if (selected.stateId) setSelectedStateId(selected.stateId);

      syncLocationTelemetry(selected.coordinates, selected.name, selected.stateId);
    },
    [syncLocationTelemetry]
  );

  const saveLocationItem = useCallback((location: Omit<SavedLocationItem, 'id'>) => {
    const updated = LocationService.saveLocation(location);
    setSavedLocations(updated);
  }, []);

  const removeLocationItem = useCallback((id: string) => {
    const updated = LocationService.removeLocation(id);
    setSavedLocations(updated);
  }, []);

  // Backward compatibility
  const setSelectedCity = useCallback(
    (cityKey: string) => {
      const key = cityKey.toLowerCase();
      setSelectedCityKey(key);
      const match = INDIAN_CITIES_REGISTRY.find((c) => c.name.toLowerCase().includes(key) || c.id.includes(key));
      if (match) {
        selectLocationItem(match);
      }
    },
    [selectLocationItem]
  );

  const setSelectedStateById = useCallback(
    (stateId: string) => {
      setSelectedStateId(stateId);
      const state = DEMO_STATES.find((s) => s.id === stateId);
      if (state) {
        const capitalCity = state.capital.split(' ')[0];
        const match = INDIAN_CITIES_REGISTRY.find((c) => c.name.toLowerCase().includes(capitalCity.toLowerCase()));
        if (match) {
          selectLocationItem(match);
        }
      }
    },
    [selectLocationItem]
  );

  const resetToNational = useCallback(() => {
    setIsNationalOverview(true);
    setSelectedStateId(null);
  }, []);

  const detectCurrentLocation = useCallback(() => {
    requestCurrentGPS();
  }, [requestCurrentGPS]);

  // Initial load: Attempt automatic GPS acquisition on launch, fallback to saved or Mumbai
  useEffect(() => {
    let isMounted = true;

    const initLocation = async () => {
      // 1. Check if browser supports geolocation and try live GPS
      if (typeof window !== 'undefined' && navigator.geolocation) {
        try {
          const success = await requestCurrentGPS();
          if (success || !isMounted) return;
        } catch (e) {
          console.warn('[LocationContext] Automatic GPS request skipped/denied:', e);
        }
      }

      // 2. Fallback to default/saved station if GPS was unavailable or denied
      if (isMounted) {
        selectLocationItem('Mumbai');
      }
    };

    initLocation();

    return () => {
      isMounted = false;
    };
  }, [requestCurrentGPS, selectLocationItem]);

  return (
    <LocationContext.Provider
      value={{
        selectedLocation,
        selectedCityKey,
        weather,
        selectedState,
        statesList: DEMO_STATES,
        savedLocations,
        userCoordinates,
        isGpsActive,
        isLoadingLocation,
        isLoadingWeather,
        locationError,
        clearLocationError,
        requestCurrentGPS,
        searchAndSelectLocation,
        selectLocationItem,
        saveLocationItem,
        removeLocationItem,
        setSelectedCity,
        setSelectedStateById,
        detectCurrentLocation,
        resetToNational,
        isNationalOverview,
      }}
    >
      {children}
    </LocationContext.Provider>
  );
};

export const useLocation = () => {
  const context = useContext(LocationContext);
  if (!context) {
    throw new Error('useLocation must be used within a LocationProvider');
  }
  return context;
};
