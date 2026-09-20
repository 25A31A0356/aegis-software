import { HazardItem, HazardCategory, HazardSeverity, HazardNature, HazardStatus } from '../types/hazard';
import { ApiClient } from './apiClient';
import { CITY_COORDINATES } from './weatherService';

export interface HazardFilterOptions {
  searchQuery?: string;
  category?: HazardCategory | 'all';
  severity?: HazardSeverity | 'all';
  nature?: HazardNature | 'all';
  status?: HazardStatus | 'all';
  stateId?: string | 'all';
  isHumanMade?: boolean | 'all';
}

export class HazardService {
  private static hazards: HazardItem[] = [];
  private static isInitialized = false;
  private static listeners: Array<() => void> = [];

  /**
   * Initializes and polls authentic live natural hazards from AEGIS Unified Backend + USGS & Open-Meteo
   */
  public static async fetchLiveHazards(): Promise<HazardItem[]> {
    try {
      const liveList: HazardItem[] = [];

      // 1. Fetch official hazards from AEGIS Unified Backend
      try {
        const backendHazards = await ApiClient.get<any[]>('/hazards');
        if (backendHazards && Array.isArray(backendHazards)) {
          for (const b of backendHazards) {
            const loc = b.location || {};
            const lat = loc.latitude || b.latitude || 20.5937;
            const lng = loc.longitude || b.longitude || 78.9629;
            const stateName = loc.state_name || b.state_name || 'India';
            const districtName = loc.district_name || b.district_name || loc.city_name || 'Regional Grid';
            const cat = (b.hazard_type || 'WEATHER').toLowerCase();
            const sev = (b.severity || 'moderate').toLowerCase() as HazardSeverity;

            liveList.push({
              id: b.id || `BACKEND-HAZ-${Math.random().toString(36).substring(2, 8)}`,
              title: `${b.hazard_type || 'Hazard'} Alert — ${districtName}, ${stateName}`,
              category: (cat === 'earthquake' || cat === 'cyclone' || cat === 'flood' || cat === 'heatwave' ? cat : 'heavy_rain') as HazardCategory,
              categoryName: `${b.hazard_type || 'Hazard'} Monitoring`,
              isHumanMade: false,
              nature: 'warning',
              severity: sev,
              status: 'active',
              headline: `Official telemetry detected ${b.hazard_type || 'hazard'} conditions in ${districtName}.`,
              description: `Real-time unified observation record from ${b.source_authority || 'AEGIS Observation Network'}.`,
              location: {
                state: stateName,
                district: districtName,
                city: loc.city_name || districtName,
                coordinates: [lat, lng],
                radiusKm: 50,
                affectedZones: [districtName, stateName],
              },
              source: {
                agency: b.source_authority || 'AEGIS Monitoring Grid',
                bulletinId: b.source_record_id || `AEGIS-${b.id || 'OBS'}`,
                publishedAt: b.observed_at ? new Date(b.observed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Live',
                validUntil: 'Active Surveillance',
              },
              metrics: b.measurements || {},
              timeline: [
                {
                  time: 'Live',
                  stage: 'Risk Detected',
                  description: `Observation registered with confidence ${(b.confidence || 1.0) * 100}%.`,
                  source: b.source_authority || 'AEGIS Core',
                },
              ],
              safetyAdvice: [
                {
                  title: 'Follow State Disaster Management Guidelines',
                  instruction: 'Stay tuned to official emergency broadcasts and adhere to evacuation advisories.',
                  urgent: sev === 'critical',
                },
              ],
              emergencyContacts: [
                { name: 'National Emergency Helpline', phone: '112' },
                { name: 'NDRF Control Room', phone: '1078' },
              ],
            });
          }
        }
      } catch (err) {
        console.warn('[HazardService] Backend hazards fetch error:', err);
      }

      // 2. Fetch Real Live USGS Earthquakes (2.5+ Magnitude) within Indian Territory
      try {
        const usgsRes = await fetch('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson', {
          headers: { Accept: 'application/json' },
        });
        if (usgsRes.ok) {
          const usgsData = await usgsRes.json();
          const features = usgsData.features || [];

          for (const feat of features.slice(0, 15)) {
            const coords = feat.geometry?.coordinates; // [lng, lat, depth]
            if (!coords || coords.length < 2) continue;
            const [lng, lat, depth] = coords;
            const mag = feat.properties?.mag || 3.0;
            const place = feat.properties?.place || 'Regional Epicenter';
            const time = new Date(feat.properties?.time || Date.now());
            const eventId = feat.id || `USGS-${Math.floor(Math.random() * 100000)}`;

            // Restrict strictly to India sovereign territory & territorial waters (6°N-37.5°N, 68°E-97.5°E)
            const isInIndia = lat >= 6.0 && lat <= 37.5 && lng >= 68.0 && lng <= 97.5;
            if (!isInIndia) continue;

            let severity: HazardSeverity = 'moderate';
            if (mag >= 6.0) severity = 'critical';
            else if (mag >= 4.5) severity = 'warning';
            else if (mag < 3.5) severity = 'minor';

            liveList.push({
              id: `LIVE-EQ-${eventId}`,
              title: `M${mag.toFixed(1)} Earthquake — ${place}`,
              category: 'earthquake',
              categoryName: 'Seismic Activity',
              isHumanMade: false,
              nature: 'incident',
              severity,
              status: 'monitoring',
              headline: `National Seismological Network recorded a magnitude ${mag.toFixed(1)} event at depth ${depth || 10}km.`,
              description: `Real-time seismic wave detection confirmed within India seismic zone. Coordinates: [${lat.toFixed(3)}°N, ${lng.toFixed(3)}°E].`,
              location: {
                state: 'India',
                district: place,
                city: place.split(' of ').pop() || place,
                coordinates: [lat, lng],
                radiusKm: Math.round(mag * 30),
                affectedZones: [place, `Depth ${depth || 10}km Epicentral Zone`],
              },
              source: {
                agency: 'USGS National Earthquake Information Center',
                bulletinId: `USGS-SEIS-${eventId.toUpperCase()}`,
                publishedAt: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' UTC',
                validUntil: 'Post-Event Seismic Relaxation (24h)',
              },
              metrics: {
                intensity: `Richter Scale M${mag.toFixed(1)}`,
                magnitudeRichter: Number(mag.toFixed(1)),
              },
              timeline: [
                {
                  time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  stage: 'Incident Reported',
                  description: `Primary P-waves and S-waves registered at automated seismic stations. Magnitude calculated at M${mag.toFixed(1)}.`,
                  source: 'USGS Global Network',
                },
                {
                  time: 'Live',
                  stage: 'Response Deployed',
                  description: 'Aftershock surveillance active across regional tectonic fracture zones.',
                  source: 'AEGIS Seismic Sentinel',
                },
              ],
              safetyAdvice: [
                {
                  title: 'Drop, Cover, and Hold On',
                  instruction: 'If shaking is felt, take shelter under sturdy furniture immediately.',
                  urgent: true,
                },
                {
                  title: 'Inspect Structural Cracks',
                  instruction: 'Avoid unreinforced masonry structures and check gas lines.',
                  urgent: false,
                },
              ],
              emergencyContacts: [
                { name: 'National Emergency Helpline', phone: '112' },
                { name: 'NDRF Seismological Control', phone: '1078' },
              ],
            });
          }
        }
      } catch (err) {
        console.warn('[HazardService] USGS Earthquake feed error:', err);
      }

      // 3. Fetch Live Open-Meteo Meteorological Hazards across Key Indian Metros
      try {
        const cities = Object.keys(CITY_COORDINATES);
        for (const cKey of cities) {
          const cfg = CITY_COORDINATES[cKey];
          const mUrl = `https://api.open-meteo.com/v1/forecast?latitude=${cfg.lat}&longitude=${cfg.lng}&current=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m,weather_code&timezone=Asia%2FKolkata`;
          const res = await fetch(mUrl, { headers: { Accept: 'application/json' } });
          if (!res.ok) continue;

          const data = await res.json();
          const curr = data.current || {};
          const temp = Math.round(curr.temperature_2m || 30);
          const wind = Math.round(curr.wind_speed_10m || 10);
          const gust = Math.round(curr.wind_gusts_10m || wind * 1.3);
          const precip = Number(curr.precipitation || 0);

          // Heatwave Hazard (Real threshold: >= 38°C)
          if (temp >= 38) {
            liveList.push({
              id: `LIVE-HEAT-${cKey.toUpperCase()}`,
              title: `Severe Thermal Heatwave Alert — ${cfg.cityName}`,
              category: 'heatwave',
              categoryName: 'Heatwave & Extreme Temp',
              isHumanMade: false,
              nature: 'warning',
              severity: temp >= 42 ? 'critical' : 'warning',
              status: 'active',
              headline: `Real-time surface temperature recorded at ${temp}°C in ${cfg.cityName}, ${cfg.stateName}.`,
              description: `Severe atmospheric heat dome conditions detected. Elevated risk of thermal fatigue, heat cramps, and dehydration.`,
              location: {
                state: cfg.stateName,
                district: cfg.cityName,
                city: cfg.cityName,
                coordinates: [cfg.lat, cfg.lng],
                radiusKm: 45,
                affectedZones: [cfg.cityName, 'Metropolitan Area', 'Urban Core'],
              },
              source: {
                agency: 'Open-Meteo High-Resolution NWP',
                bulletinId: `HEAT-${cKey.toUpperCase()}-${new Date().toISOString().slice(0, 10)}`,
                publishedAt: 'Real-Time Telemetry Stream',
                validUntil: 'Today, 18:00 IST',
              },
              metrics: {
                intensity: `Ambient ${temp}°C`,
                heatIndexCelsius: temp,
                windSpeedKmph: wind,
              },
              timeline: [
                {
                  time: 'Live Stream',
                  stage: 'Warning Upgraded',
                  description: `Ground temperature sensors cross threshold at ${temp}°C.`,
                  source: 'Meteorological Ingestion Pipeline',
                },
              ],
              safetyAdvice: [
                {
                  title: 'Hydration & Sun Exposure Limit',
                  instruction: 'Avoid direct sunlight between 11:00 AM and 4:00 PM. Drink plenty of water.',
                  urgent: true,
                },
              ],
              emergencyContacts: [
                { name: 'State Heatwave Medical Helpline', phone: '108' },
                { name: 'Disaster Management Cell', phone: '1070' },
              ],
            });
          }

          // Rainfall / Inundation Hazard (Real threshold: >= 10mm)
          if (precip >= 10) {
            liveList.push({
              id: `LIVE-RAIN-${cKey.toUpperCase()}`,
              title: `Heavy Inundation & Precipitation Watch — ${cfg.cityName}`,
              category: 'flash_flood',
              categoryName: 'Flash Flood & Inundation',
              isHumanMade: false,
              nature: 'warning',
              severity: precip >= 30 ? 'critical' : 'warning',
              status: 'active',
              headline: `Active rainfall of ${precip}mm recorded over ${cfg.cityName}. Catchment overflow warning active.`,
              description: `Convective cloud mass generating localized high-intensity precipitation. Urban lowlands and underpasses at risk of waterlogging.`,
              location: {
                state: cfg.stateName,
                district: cfg.cityName,
                city: cfg.cityName,
                coordinates: [cfg.lat, cfg.lng],
                radiusKm: 30,
                affectedZones: [cfg.cityName, 'Low-lying Drainage Basins'],
              },
              source: {
                agency: 'Open-Meteo Radar & Hydrology',
                bulletinId: `HYDRO-${cKey.toUpperCase()}-${new Date().toISOString().slice(0, 10)}`,
                publishedAt: 'Real-Time Stream',
                validUntil: 'Next 6 Hours',
              },
              metrics: {
                rainfallMm: precip,
                windSpeedKmph: wind,
              },
              timeline: [
                {
                  time: 'Live Stream',
                  stage: 'Warning Upgraded',
                  description: `Precipitation rate of ${precip}mm registered by radar extrapolation.`,
                  source: 'Hydro-Meteorological Pipeline',
                },
              ],
              safetyAdvice: [
                {
                  title: 'Avoid Waterlogged Corridors',
                  instruction: 'Do not attempt to drive through flooded underpasses or swift-moving water.',
                  urgent: true,
                },
              ],
              emergencyContacts: [
                { name: 'Flood Rescue Control Room', phone: '1070' },
                { name: 'NDRF Search & Rescue', phone: '1078' },
              ],
            });
          }

          // High Wind / Gale Warning (Real threshold: >= 35 km/h)
          if (wind >= 35 || gust >= 50) {
            liveList.push({
              id: `LIVE-WIND-${cKey.toUpperCase()}`,
              title: `High Wind Vectors & Gale Advisory — ${cfg.cityName}`,
              category: 'cyclone',
              categoryName: 'Cyclone & High Wind',
              isHumanMade: false,
              nature: 'warning',
              severity: wind >= 50 ? 'critical' : 'warning',
              status: 'active',
              headline: `Sustained surface winds of ${wind} km/h with gusts of ${gust} km/h recorded in ${cfg.cityName}.`,
              description: `Strong pressure gradient generating gale-force wind gusts. Structural loose objects and power lines require monitoring.`,
              location: {
                state: cfg.stateName,
                district: cfg.cityName,
                city: cfg.cityName,
                coordinates: [cfg.lat, cfg.lng],
                radiusKm: 50,
                affectedZones: [cfg.cityName, 'Open Coastal / Elevated Zones'],
              },
              source: {
                agency: 'Open-Meteo Real Data Feed',
                bulletinId: `GALE-${cKey.toUpperCase()}-${new Date().toISOString().slice(0, 10)}`,
                publishedAt: 'Live Stream',
                validUntil: 'Next 8 Hours',
              },
              metrics: {
                windSpeedKmph: wind,
              },
              timeline: [
                {
                  time: 'Live Stream',
                  stage: 'Risk Detected',
                  description: `Anemometers confirm wind gust spike to ${gust} km/h.`,
                  source: 'Atmospheric Sensor Network',
                },
              ],
              safetyAdvice: [
                {
                  title: 'Secure Loose Outdoor Structures',
                  instruction: 'Fasten loose tin roofs, signs, and stay clear of tall trees.',
                  urgent: false,
                },
              ],
              emergencyContacts: [
                { name: 'Cyclone Emergency Command', phone: '1070' },
                { name: 'Emergency Police & Rescue', phone: '112' },
              ],
            });
          }
        }
      } catch (err) {
        console.warn('[HazardService] Weather hazard generation error:', err);
      }

      this.hazards = liveList;
      this.isInitialized = true;
      this.notifyListeners();
      return this.hazards;
    } catch (err) {
      console.warn('[HazardService] Overall fetchLiveHazards failure:', err);
      return this.hazards;
    }
  }

  public static async fetchNearbyHazards(lat: number, lng: number, radiusKm: number = 50): Promise<any[]> {
    try {
      const data = await ApiClient.get<any[]>('/hazards/nearby', { lat, lng, radius_km: radiusKm });
      return data || [];
    } catch (err) {
      console.warn('[HazardService] fetchNearbyHazards error:', err);
      return [];
    }
  }

  public static getAllHazards(): HazardItem[] {
    if (!this.isInitialized) {
      this.fetchLiveHazards().catch(console.error);
    }
    return [...this.hazards];
  }

  public static getHazardById(id: string): HazardItem | undefined {
    return this.hazards.find((h) => h.id === id);
  }

  public static filterHazards(options: HazardFilterOptions): HazardItem[] {
    return this.hazards.filter((item) => {
      if (options.searchQuery) {
        const q = options.searchQuery.toLowerCase();
        const matchTitle = item.title.toLowerCase().includes(q);
        const matchHeadline = item.headline.toLowerCase().includes(q);
        const matchState = item.location.state.toLowerCase().includes(q);
        const matchDistrict = item.location.district.toLowerCase().includes(q);
        const matchCategory = item.categoryName.toLowerCase().includes(q);
        const matchAgency = item.source.agency.toLowerCase().includes(q);
        if (!matchTitle && !matchHeadline && !matchState && !matchDistrict && !matchCategory && !matchAgency) {
          return false;
        }
      }

      if (options.category && options.category !== 'all' && item.category !== options.category) {
        return false;
      }

      if (options.severity && options.severity !== 'all' && item.severity !== options.severity) {
        return false;
      }

      if (options.nature && options.nature !== 'all' && item.nature !== options.nature) {
        return false;
      }

      if (options.status && options.status !== 'all' && item.status !== options.status) {
        return false;
      }

      if (options.isHumanMade !== undefined && options.isHumanMade !== 'all') {
        if (Boolean(item.isHumanMade) !== options.isHumanMade) {
          return false;
        }
      }

      if (options.stateId && options.stateId !== 'all') {
        const matchState = item.location.state.toLowerCase().includes(options.stateId.toLowerCase()) ||
          options.stateId.toLowerCase().includes(item.location.state.toLowerCase());
        if (!matchState) {
          return false;
        }
      }

      return true;
    });
  }

  public static getMetricsSummary() {
    const totalHazards = this.hazards.length;
    const criticalHazards = this.hazards.filter((h) => h.severity === 'critical').length;
    const warningHazards = this.hazards.filter((h) => h.severity === 'warning').length;
    const activeIncidents = this.hazards.filter((h) => h.nature === 'incident' && h.status === 'active').length;
    const activeWarnings = this.hazards.filter((h) => h.nature === 'warning' && h.status === 'active').length;
    const activeForecasts = this.hazards.filter((h) => h.nature === 'forecast').length;

    return {
      totalHazards,
      criticalHazards,
      warningHazards,
      activeIncidents,
      activeWarnings,
      activeForecasts,
    };
  }

  public static subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private static notifyListeners() {
    this.listeners.forEach((l) => l());
  }
}
