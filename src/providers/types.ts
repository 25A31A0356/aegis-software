/**
 * AEGIS ALERT - Data Provider Architecture Types
 * Defines strict interfaces for Weather, Disaster Alerts, Geocoding, Maps, Radar, Satellite, and Lightning providers.
 * Supports dual DATA_MODE: 'LIVE' vs 'DEMO'.
 */

import { WeatherTelemetry } from '../types/weather';
import { HazardItem } from '../types/hazard';

export type DataMode = 'LIVE' | 'DEMO';

export interface ProviderResult<T> {
  data: T;
  mode: DataMode;
  sourceName: string;
  sourceAuthority: string;
  authorityUrl?: string;
  isLive: boolean;
  timestamp: string;
  disclaimer?: string;
}

export interface ProviderHealth {
  providerId: string;
  name: string;
  serviceType: 'weather' | 'alerts' | 'geocoding' | 'maps' | 'radar' | 'satellite' | 'lightning';
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE' | 'DEMO_FALLBACK';
  mode: DataMode;
  latencyMs: number;
  lastSync: string;
  authoritySource: string;
  description: string;
}

// 1. Weather Provider Interface
export interface IWeatherProvider {
  getWeatherByCoordinates(lat: number, lng: number): Promise<ProviderResult<WeatherTelemetry>>;
  getWeatherByCityKey(cityKey: string): Promise<ProviderResult<WeatherTelemetry>>;
}

// 2. Disaster Alerts Provider Interface
export interface IDisasterAlertsProvider {
  getActiveAlerts(filter?: any): Promise<ProviderResult<HazardItem[]>>;
  getNearbyAlerts(lat: number, lng: number, radiusKm?: number): Promise<ProviderResult<HazardItem[]>>;
}

// 3. Geocoding Provider Interface
export interface GeocodedLocationItem {
  id: string;
  name: string;
  stateName: string;
  district: string;
  stateId: string;
  country: string;
  coordinates: [number, number]; // [lat, lng]
  readableAddress: string;
  confidenceScore: number;
}

export interface IGeocodingProvider {
  searchLocation(query: string): Promise<ProviderResult<GeocodedLocationItem[]>>;
  reverseGeocode(lat: number, lng: number): Promise<ProviderResult<GeocodedLocationItem>>;
}

// 4. Map Provider Interface
export interface TileLayerConfig {
  id: string;
  name: string;
  style: 'streets' | 'satellite' | 'terrain' | 'dark' | 'hydrological' | 'thermal';
  url: string;
  attribution: string;
  maxZoom: number;
  subdomains?: string[];
}

export interface IMapProvider {
  getTileLayer(style: 'streets' | 'satellite' | 'terrain' | 'dark' | 'hydrological' | 'thermal'): ProviderResult<TileLayerConfig>;
  getAvailableTileLayers(): ProviderResult<TileLayerConfig[]>;
}

// 5. Radar Provider Interface
export interface RadarStormCell {
  id: string;
  center: [number, number];
  reflectivityDbz: number;
  intensityLabel: 'Light' | 'Moderate' | 'Heavy Inundation' | 'Severe Hail/Cloudburst';
  movementVector: {
    headingDeg: number;
    speedKmh: number;
  };
  cloudTopKm: number;
  radiusKm: number;
  stationOrigin: string;
  updatedAt: string;
}

export interface IRadarProvider {
  getRadarStormCells(center: [number, number]): Promise<ProviderResult<RadarStormCell[]>>;
}

// 6. Satellite Provider Interface
export interface SatelliteBandTelemetry {
  satelliteId: string;
  satelliteName: string;
  sector: string;
  channel: 'TIR-1 (Thermal Infrared)' | 'VIS (Visible High Res)' | 'WV (Water Vapor)' | 'SWIR (Short Wave)';
  cloudMotionVectorsAvailable: boolean;
  cycloneVortexIdentified: boolean;
  seaSurfaceTempCelsius?: number;
  imageryTimestamp: string;
  coverageBounds: {
    minLat: number;
    maxLat: number;
    minLng: number;
    maxLng: number;
  };
  tileUrlPattern?: string;
}

export interface ISatelliteProvider {
  getSatelliteBandInfo(channel?: string): Promise<ProviderResult<SatelliteBandTelemetry>>;
}

// 7. Lightning Provider Interface
export interface LightningStrikeEvent {
  id: string;
  coordinates: [number, number];
  peakCurrentKiloAmps: number;
  polarity: 'POSITIVE' | 'NEGATIVE';
  groundDischargeType: 'Cloud-to-Ground (CG)' | 'Intra-Cloud (IC)';
  timestampEpochMs: number;
  formattedTime: string;
  distanceKm?: number;
}

export interface ILightningProvider {
  getLightningStrikes(center: [number, number], radiusKm?: number): Promise<ProviderResult<LightningStrikeEvent[]>>;
}
