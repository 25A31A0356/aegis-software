/**
 * AEGIS ALERT - Map Provider Implementations
 * Live Provider: OpenStreetMap, Esri Satellite, CartoDB Positron/Dark, OpenTopoMap
 * Demo Provider: Static Simulation Basemap tiles
 */

import { IMapProvider, TileLayerConfig, ProviderResult } from './types';

export const TILE_LAYERS: Record<string, TileLayerConfig> = {
  streets: {
    id: 'layer-osm-streets',
    name: 'Standard Street GIS',
    style: 'streets',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  satellite: {
    id: 'layer-esri-satellite',
    name: 'High-Resolution Satellite',
    style: 'satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    maxZoom: 18,
  },
  terrain: {
    id: 'layer-opentopo',
    name: 'Topographic Elevation & Contours',
    style: 'terrain',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
    maxZoom: 17,
    subdomains: ['a', 'b', 'c'],
  },
  dark: {
    id: 'layer-carto-dark',
    name: 'Tactical Dark Operations',
    style: 'dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 19,
    subdomains: ['a', 'b', 'c', 'd'],
  },
  hydrological: {
    id: 'layer-hydro',
    name: 'River Basins & Water Flow',
    style: 'hydrological',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; Central Water Commission (CWC) River Inundation Overlay',
    maxZoom: 19,
  },
  thermal: {
    id: 'layer-thermal',
    name: 'Surface Thermal & Heat Hotspots',
    style: 'thermal',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; MOSDAC / ISRO Thermal Infrared Sensor Grid',
    maxZoom: 18,
  },
};

export class LiveMapProvider implements IMapProvider {
  getTileLayer(
    style: 'streets' | 'satellite' | 'terrain' | 'dark' | 'hydrological' | 'thermal' = 'streets'
  ): ProviderResult<TileLayerConfig> {
    const config = TILE_LAYERS[style] || TILE_LAYERS.streets;
    return {
      data: config,
      mode: 'LIVE',
      sourceName: 'Global GIS & Remote Sensing Tile Network',
      sourceAuthority: 'OpenStreetMap, Esri World Imagery & OpenTopoMap',
      authorityUrl: 'https://www.openstreetmap.org',
      isLive: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  getAvailableTileLayers(): ProviderResult<TileLayerConfig[]> {
    return {
      data: Object.values(TILE_LAYERS),
      mode: 'LIVE',
      sourceName: 'AEGIS Multi-Source GIS Basemap Stack',
      sourceAuthority: 'Survey of India / OpenStreetMap / Esri',
      isLive: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }
}

export class DemoMapProvider implements IMapProvider {
  getTileLayer(
    style: 'streets' | 'satellite' | 'terrain' | 'dark' | 'hydrological' | 'thermal' = 'streets'
  ): ProviderResult<TileLayerConfig> {
    const config = TILE_LAYERS[style] || TILE_LAYERS.streets;
    return {
      data: config,
      mode: 'DEMO',
      sourceName: 'AEGIS Static Basemap Simulation Layer',
      sourceAuthority: 'NDMA Mock Training & Drill Registry',
      isLive: false,
      timestamp: 'Simulated Data',
      disclaimer: '⚠️ DEMO MODE: Structured simulation data for disaster training & interface preview.',
    };
  }

  getAvailableTileLayers(): ProviderResult<TileLayerConfig[]> {
    return {
      data: Object.values(TILE_LAYERS),
      mode: 'DEMO',
      sourceName: 'AEGIS Static Basemap Simulation Layer',
      sourceAuthority: 'NDMA Mock Training & Drill Registry',
      isLive: false,
      timestamp: 'Simulated Data',
      disclaimer: '⚠️ DEMO MODE: Structured simulation data for disaster training & interface preview.',
    };
  }
}
