/**
 * AEGIS ALERT - Disaster Alerts Provider Implementations
 * Live Provider: National Disaster Management Authority (NDMA) & SACHET CAP Feed
 * Demo Provider: Structured Multi-Hazard Simulation Dataset
 */

import { IDisasterAlertsProvider, ProviderResult } from './types';
import { HazardService } from '../services/hazardService';

export class LiveAlertsProvider implements IDisasterAlertsProvider {
  async getActiveAlerts(filter?: any): Promise<ProviderResult<any[]>> {
    try {
      const res = await fetch('/api/alerts');
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          return {
            data: json.data,
            mode: 'LIVE',
            sourceName: 'CAP India Alerting Gateway (NDMA/IMD/CWC)',
            sourceAuthority: 'National Disaster Management Authority & IMD',
            authorityUrl: 'https://cap.ndma.gov.in',
            isLive: true,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          };
        }
      }
    } catch (e) {
      console.warn('[LiveAlertsProvider] Backend alerts fetch failed:', e);
    }

    const fallback = new DemoAlertsProvider();
    return fallback.getActiveAlerts(filter);
  }

  async getNearbyAlerts(lat: number, lng: number, radiusKm: number = 100): Promise<ProviderResult<any[]>> {
    try {
      const res = await fetch(`/api/alerts/nearby?lat=${lat}&lng=${lng}&radiusKm=${radiusKm}`);
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          return {
            data: json.data,
            mode: 'LIVE',
            sourceName: 'Regional Disaster Warning Radar Hub',
            sourceAuthority: 'State Emergency Operations Center (SEOC)',
            isLive: true,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          };
        }
      }
    } catch {}

    const fallback = new DemoAlertsProvider();
    return fallback.getNearbyAlerts(lat, lng, radiusKm);
  }
}

export class DemoAlertsProvider implements IDisasterAlertsProvider {
  async getActiveAlerts(filter?: any): Promise<ProviderResult<any[]>> {
    const hazards = HazardService.getAllHazards();
    return {
      data: hazards,
      mode: 'DEMO',
      sourceName: 'AEGIS Mock Disaster Scenario Dataset',
      sourceAuthority: 'NDMA Mock Training & Drill Registry',
      isLive: false,
      timestamp: 'Simulated Data',
      disclaimer: '⚠️ DEMO MODE: Structured simulation data for disaster training & interface preview.',
    };
  }

  async getNearbyAlerts(lat: number, lng: number, radiusKm: number = 100): Promise<ProviderResult<any[]>> {
    const hazards = HazardService.getAllHazards().slice(0, 3);
    return {
      data: hazards,
      mode: 'DEMO',
      sourceName: 'AEGIS Mock Disaster Scenario Dataset',
      sourceAuthority: 'NDMA Mock Training & Drill Registry',
      isLive: false,
      timestamp: 'Simulated Data',
      disclaimer: '⚠️ DEMO MODE: Structured simulation data for disaster training & interface preview.',
    };
  }
}
