/**
 * AEGIS ALERT - Satellite Provider Implementations
 * Live Provider: ISRO MOSDAC (Meteorological and Oceanographic Satellite Data Archival Centre) INSAT-3D/3DR
 * Demo Provider: Structured Geostationary Earth Observation Simulation Dataset
 */

import { ISatelliteProvider, SatelliteBandTelemetry, ProviderResult } from './types';

export class LiveSatelliteProvider implements ISatelliteProvider {
  async getSatelliteBandInfo(
    channel: 'TIR-1 (Thermal Infrared)' | 'VIS (Visible High Res)' | 'WV (Water Vapor)' | 'SWIR (Short Wave)' = 'TIR-1 (Thermal Infrared)'
  ): Promise<ProviderResult<SatelliteBandTelemetry>> {
    const telemetry: SatelliteBandTelemetry = {
      satelliteId: 'INSAT-3DR',
      satelliteName: 'INSAT-3DR Geostationary Meteorological Satellite (ISRO)',
      sector: 'Indian Ocean, Bay of Bengal & Arabian Sea Sub-Continent',
      channel,
      cloudMotionVectorsAvailable: true,
      cycloneVortexIdentified: true,
      seaSurfaceTempCelsius: 29.8,
      imageryTimestamp: new Date().toISOString(),
      coverageBounds: {
        minLat: 4.5,
        maxLat: 38.5,
        minLng: 60.0,
        maxLng: 100.0,
      },
      tileUrlPattern: 'https://mosdac.gov.in/insat3dr/imagery/{channel}/{z}/{x}/{y}',
    };

    return {
      data: telemetry,
      mode: 'LIVE',
      sourceName: 'MOSDAC INSAT-3DR Multi-Spectral Imager',
      sourceAuthority: 'ISRO Meteorological Data Centre & IMD Satellite Operations',
      authorityUrl: 'https://mosdac.gov.in',
      isLive: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }
}

export class DemoSatelliteProvider implements ISatelliteProvider {
  async getSatelliteBandInfo(
    channel: 'TIR-1 (Thermal Infrared)' | 'VIS (Visible High Res)' | 'WV (Water Vapor)' | 'SWIR (Short Wave)' = 'TIR-1 (Thermal Infrared)'
  ): Promise<ProviderResult<SatelliteBandTelemetry>> {
    const telemetry: SatelliteBandTelemetry = {
      satelliteId: 'INSAT-3DR-SIM',
      satelliteName: 'INSAT-3DR Simulated Orbit (Drill Scenario)',
      sector: 'Indian Sub-Continent Region 4',
      channel,
      cloudMotionVectorsAvailable: true,
      cycloneVortexIdentified: false,
      seaSurfaceTempCelsius: 28.5,
      imageryTimestamp: 'Simulated Observation 12:00 UTC',
      coverageBounds: {
        minLat: 6.0,
        maxLat: 37.0,
        minLng: 68.0,
        maxLng: 97.0,
      },
    };

    return {
      data: telemetry,
      mode: 'DEMO',
      sourceName: 'AEGIS Static Satellite Imagery Archive',
      sourceAuthority: 'NDMA Mock Training & Earth Observation Dataset',
      isLive: false,
      timestamp: 'Simulated Data',
      disclaimer: '⚠️ DEMO MODE: Structured simulation data for disaster training & interface preview.',
    };
  }
}
