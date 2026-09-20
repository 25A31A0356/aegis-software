/**
 * AGIES Map Service - GIS & Technical Layers Abstraction
 * Handles tile providers (Satellite, Radar, Streets, Terrain), radar precipitation reflectivity contours, and lightning telemetry.
 */
import { ApiClient } from './apiClient';

export interface MapTileProvider {
  id: string;
  name: string;
  url: string;
  attribution: string;
  maxZoom?: number;
}

export interface RadarStormCell {
  id: string;
  center: [number, number];
  intensity: 'light' | 'moderate' | 'heavy';
  radiusMeters: number;
  dbz: number;
  movementHeading: string;
  speedKmh: number;
}

export interface LightningStrike {
  id: string;
  coordinates: [number, number];
  timestamp: string;
  peakCurrentKa: number;
  type: 'cloud-to-ground' | 'intra-cloud';
}

class MapServiceClass {
  // Safe Tile Providers
  private providers: Record<string, MapTileProvider> = {
    streets: {
      id: 'streets',
      name: 'Standard Streets (OSM)',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    },
    cartoLight: {
      id: 'cartoLight',
      name: 'CartoDB Positron',
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    },
    satellite: {
      id: 'satellite',
      name: 'Esri World Imagery (Satellite)',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
      maxZoom: 18,
    },
    terrain: {
      id: 'terrain',
      name: 'OpenTopoMap (Terrain)',
      url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
      attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
      maxZoom: 17,
    },
  };

  private lightningCache: LightningStrike[] = [];
  private radarCache: Record<string, RadarStormCell[]> = {};

  /**
   * Returns tile layer configuration for a given layer style
   */
  getTileProvider(layerStyle: 'satellite' | 'streets' | 'terrain' | 'dark' = 'streets'): MapTileProvider {
    if (layerStyle === 'satellite') return this.providers.satellite;
    if (layerStyle === 'terrain') return this.providers.terrain;
    return this.providers.cartoLight || this.providers.streets;
  }

  /**
   * Fetches real lightning strikes from backend /api/v1/lightning
   */
  async fetchLiveLightning(lat?: number, lng?: number): Promise<LightningStrike[]> {
    try {
      const data = await ApiClient.get<any[]>('/lightning', { lat, lng, limit: 50 });
      if (data && Array.isArray(data)) {
        this.lightningCache = data.map((item) => ({
          id: item.id || `lt-${Math.random().toString(36).substring(2, 7)}`,
          coordinates: [item.latitude || 20.59, item.longitude || 78.96],
          timestamp: item.observed_at ? new Date(item.observed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Live',
          peakCurrentKa: item.peak_current_ka || 25,
          type: item.flash_rate_per_min > 20 ? 'cloud-to-ground' : 'intra-cloud',
        }));
        return this.lightningCache;
      }
    } catch (err) {
      console.warn('[MapService] fetchLiveLightning error:', err);
    }
    return this.lightningCache;
  }

  /**
   * Returns active lightning flash strikes in the region
   */
  getRegionalLightningStrikes(center: [number, number]): LightningStrike[] {
    this.fetchLiveLightning(center[0], center[1]).catch(console.warn);
    return this.lightningCache;
  }

  /**
   * Returns Doppler radar storm clusters around the active coordinates
   */
  getRadarStormCells(center: [number, number]): RadarStormCell[] {
    const key = `${center[0].toFixed(2)}_${center[1].toFixed(2)}`;
    return this.radarCache[key] || [];
  }

  /**
   * Returns color code corresponding to radar intensity
   */
  getRadarIntensityColor(intensity: 'light' | 'moderate' | 'heavy'): { fill: string; stroke: string } {
    switch (intensity) {
      case 'heavy':
        return { fill: '#E94B68', stroke: '#B82842' }; // Red/Crimson
      case 'moderate':
        return { fill: '#F4C84A', stroke: '#C89618' }; // Yellow/Orange
      case 'light':
      default:
        return { fill: '#45C79A', stroke: '#289870' }; // Green/Cyan
    }
  }
}

export const MapService = new MapServiceClass();
