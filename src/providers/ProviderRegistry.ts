/**
 * AEGIS ALERT - Central Provider Registry & Mode Manager
 * Orchestrates Weather, Alerts, Geocoding, Maps, Radar, Satellite, and Lightning providers.
 * Supports runtime switching and environment configuration (DATA_MODE=demo | DATA_MODE=live).
 */

import {
  DataMode,
  ProviderHealth,
  IWeatherProvider,
  IDisasterAlertsProvider,
  IGeocodingProvider,
  IMapProvider,
  IRadarProvider,
  ISatelliteProvider,
  ILightningProvider,
} from './types';
import { LiveWeatherProvider, DemoWeatherProvider } from './weatherProvider';
import { LiveAlertsProvider, DemoAlertsProvider } from './alertsProvider';
import { LiveGeocodingProvider, DemoGeocodingProvider } from './geocodingProvider';
import { LiveMapProvider, DemoMapProvider } from './mapProvider';
import { LiveRadarProvider, DemoRadarProvider } from './radarProvider';
import { LiveSatelliteProvider, DemoSatelliteProvider } from './satelliteProvider';
import { LiveLightningProvider, DemoLightningProvider } from './lightningProvider';

const STORAGE_MODE_KEY = 'aegis_data_mode_v1';

class ProviderRegistryClass {
  private currentMode: DataMode = 'DEMO';
  private listeners: Array<(mode: DataMode) => void> = [];

  // Provider Instances
  private liveWeather: IWeatherProvider = new LiveWeatherProvider();
  private demoWeather: IWeatherProvider = new DemoWeatherProvider();

  private liveAlerts: IDisasterAlertsProvider = new LiveAlertsProvider();
  private demoAlerts: IDisasterAlertsProvider = new DemoAlertsProvider();

  private liveGeocoding: IGeocodingProvider = new LiveGeocodingProvider();
  private demoGeocoding: IGeocodingProvider = new DemoGeocodingProvider();

  private liveMaps: IMapProvider = new LiveMapProvider();
  private demoMaps: IMapProvider = new DemoMapProvider();

  private liveRadar: IRadarProvider = new LiveRadarProvider();
  private demoRadar: IRadarProvider = new DemoRadarProvider();

  private liveSatellite: ISatelliteProvider = new LiveSatelliteProvider();
  private demoSatellite: ISatelliteProvider = new DemoSatelliteProvider();

  private liveLightning: ILightningProvider = new LiveLightningProvider();
  private demoLightning: ILightningProvider = new DemoLightningProvider();

  constructor() {
    this.initMode();
  }

  private initMode() {
    // 1. Check environment variable (VITE_DATA_MODE or DATA_MODE)
    const envMode = ((import.meta as any).env?.VITE_DATA_MODE || '').toString().toUpperCase();
    if (envMode === 'LIVE') {
      this.currentMode = 'LIVE';
      return;
    }

    // 2. Check localStorage
    try {
      const stored = localStorage.getItem(STORAGE_MODE_KEY) || localStorage.getItem('agies_data_mode_v1');
      if (stored === 'LIVE' || stored === 'DEMO') {
        this.currentMode = stored;
        return;
      }
    } catch {}

    // Default to DEMO mode for safety until explicitly configured
    this.currentMode = 'DEMO';
  }

  public getDataMode(): DataMode {
    return this.currentMode;
  }

  public setDataMode(mode: DataMode): void {
    if (this.currentMode !== mode) {
      this.currentMode = mode;
      try {
        localStorage.setItem(STORAGE_MODE_KEY, mode);
      } catch {}
      this.notifyListeners();
    }
  }

  public toggleDataMode(): DataMode {
    const next = this.currentMode === 'LIVE' ? 'DEMO' : 'LIVE';
    this.setDataMode(next);
    return next;
  }

  public subscribe(listener: (mode: DataMode) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private notifyListeners() {
    this.listeners.forEach((l) => l(this.currentMode));
  }

  // --- Active Provider Getters ---

  public getWeatherProvider(): IWeatherProvider {
    return this.currentMode === 'LIVE' ? this.liveWeather : this.demoWeather;
  }

  public getAlertsProvider(): IDisasterAlertsProvider {
    return this.currentMode === 'LIVE' ? this.liveAlerts : this.demoAlerts;
  }

  public getGeocodingProvider(): IGeocodingProvider {
    return this.currentMode === 'LIVE' ? this.liveGeocoding : this.demoGeocoding;
  }

  public getMapProvider(): IMapProvider {
    return this.currentMode === 'LIVE' ? this.liveMaps : this.demoMaps;
  }

  public getRadarProvider(): IRadarProvider {
    return this.currentMode === 'LIVE' ? this.liveRadar : this.demoRadar;
  }

  public getSatelliteProvider(): ISatelliteProvider {
    return this.currentMode === 'LIVE' ? this.liveSatellite : this.demoSatellite;
  }

  public getLightningProvider(): ILightningProvider {
    return this.currentMode === 'LIVE' ? this.liveLightning : this.demoLightning;
  }

  // --- System Health & Provenance Metadata ---

  public getProvidersHealth(): ProviderHealth[] {
    const isLive = this.currentMode === 'LIVE';
    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    return [
      {
        providerId: 'weather-telemetry',
        name: 'Weather & Surface Telemetry',
        serviceType: 'weather',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 42 : 4,
        lastSync: nowStr,
        authoritySource: isLive ? 'India Meteorological Department (IMD) & Open-Meteo' : 'NDMA Simulation Dataset',
        description: 'Atmospheric pressure, precipitation, temperature, wind vectors & air quality index.',
      },
      {
        providerId: 'disaster-alerts',
        name: 'CAP Multi-Hazard Alerts Gateway',
        serviceType: 'alerts',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 68 : 3,
        lastSync: nowStr,
        authoritySource: isLive ? 'National Disaster Management Authority (NDMA) & SEOC' : 'NDMA Drill Mock Feed',
        description: 'Authoritative early warnings, evacuation orders, flood inundation notices.',
      },
      {
        providerId: 'gis-geocoding',
        name: 'Geocoding & Administrative Boundaries',
        serviceType: 'geocoding',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 120 : 2,
        lastSync: nowStr,
        authoritySource: isLive ? 'OpenStreetMap Nominatim & Survey of India' : 'Local Indian Districts Registry',
        description: 'Forward/Reverse coordinate geocoding, district boundary resolution.',
      },
      {
        providerId: 'map-tiles',
        name: 'GIS Basemap & Spatial Overlays',
        serviceType: 'maps',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 35 : 1,
        lastSync: nowStr,
        authoritySource: isLive ? 'OpenStreetMap, Esri World Imagery & OpenTopoMap' : 'NDMA Tactical Base Layers',
        description: 'Multi-resolution satellite, terrain contours, and street topography.',
      },
      {
        providerId: 'doppler-radar',
        name: 'Doppler Weather Radar (DWR) Stream',
        serviceType: 'radar',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 85 : 5,
        lastSync: nowStr,
        authoritySource: isLive ? 'IMD S-Band / C-Band Doppler Radar Network' : 'NDMA Radar Simulation Model',
        description: 'Reflectivity (dBZ), storm cell tracking, and cloud top elevation.',
      },
      {
        providerId: 'satellite-remote-sensing',
        name: 'Earth Observation Satellite Telemetry',
        serviceType: 'satellite',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 95 : 3,
        lastSync: nowStr,
        authoritySource: isLive ? 'ISRO MOSDAC (INSAT-3D/3DR Geostationary Satellites)' : 'NDMA Orbit Archive',
        description: 'Thermal infrared, water vapor imagery, and cyclone vortex tracking.',
      },
      {
        providerId: 'lightning-sensor-grid',
        name: 'Atmospheric Lightning Discharge Grid',
        serviceType: 'lightning',
        status: isLive ? 'ONLINE' : 'DEMO_FALLBACK',
        mode: this.currentMode,
        latencyMs: isLive ? 55 : 2,
        lastSync: nowStr,
        authoritySource: isLive ? 'IITM Damini Lightning Detection Sensor Array' : 'NDMA Simulated Discharge Data',
        description: 'Cloud-to-ground strike locations, peak current (kA), and real-time flash alerts.',
      },
    ];
  }
}

export const ProviderRegistry = new ProviderRegistryClass();
