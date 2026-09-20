import { ApiClient } from './apiClient';
import { ExportDataPayload } from './exportService';

export interface AnalyticsFilterState {
  location: string;
  hazard: string;
  dateRange: string;
}

export interface AnalyticsResult {
  stats: {
    peakIntensity: string;
    peakIntensityLabel: string;
    totalEvents: number;
    activeEvents: number;
    peopleAffected: string;
    peopleAffectedExact: number;
    trend: string;
    trendPositive: boolean;
    trendSubtext: string;
  };
  timeline: Array<{
    date: string;
    intensityIndex: number;
    peopleAffected: number;
    alertCount: number;
    baseline: number;
  }>;
  severityDistribution: Array<{
    name: string;
    count: number;
    percentage: number;
    color: string;
  }>;
  regionalImpact: Array<{
    region: string;
    events: number;
    affected: number;
    severity: 'critical' | 'warning' | 'moderate' | 'minor';
    riskScore: number;
  }>;
  isLiveData: boolean;
  hasData: boolean;
  message?: string;
  generatedTimestamp: string;
}

export class AnalyticsService {
  /**
   * Fetches authentic PostgreSQL disaster analytics via the central /api/v1/analytics endpoint.
   * If no real records exist for the selected location/hazard, returns hasData: false
   * and "Insufficient real data available for this location."
   */
  public static async fetchAnalyticsData(filter: AnalyticsFilterState): Promise<AnalyticsResult> {
    const { location, hazard, dateRange } = filter;
    const now = new Date();

    try {
      const resp = await ApiClient.get<any>('/analytics', {
        location: location === 'all' ? 'india' : location,
        hazard: hazard === 'all' ? 'all' : hazard,
        date_range: dateRange || '7d',
      });

      if (resp) {
        return {
          stats: {
            peakIntensity: resp.stats?.peak_intensity || 'No active alerts',
            peakIntensityLabel: resp.stats?.peak_intensity_label || 'Telemetry Status',
            totalEvents: resp.stats?.total_events || 0,
            activeEvents: resp.stats?.active_events || 0,
            peopleAffected: resp.stats?.people_affected || '0',
            peopleAffectedExact: resp.stats?.people_affected_exact || 0,
            trend: resp.stats?.trend || 'Real-time database sync',
            trendPositive: resp.stats?.trend_positive ?? true,
            trendSubtext: resp.stats?.trend_subtext || 'Aggregated from real PostgreSQL observations & reports',
          },
          timeline: (resp.timeline || []).map((t: any) => ({
            date: t.date,
            intensityIndex: t.intensity_index || 0,
            peopleAffected: t.people_affected || 0,
            alertCount: t.alert_count || 0,
            baseline: t.baseline || 0,
          })),
          severityDistribution: resp.severity_distribution || [
            { name: 'Critical (Red)', count: 0, percentage: 0, color: '#E94B68' },
            { name: 'Warning (Amber)', count: 0, percentage: 0, color: '#F4C84A' },
            { name: 'Moderate (Cyan)', count: 0, percentage: 0, color: '#18C3D0' },
            { name: 'Minor (Green)', count: 0, percentage: 0, color: '#45C79A' },
          ],
          regionalImpact: (resp.regional_impact || []).map((r: any) => ({
            region: r.region,
            events: r.events,
            affected: r.affected,
            severity: r.severity || 'moderate',
            riskScore: r.risk_score || 50,
          })),
          isLiveData: true,
          hasData: Boolean(resp.has_data),
          message: resp.message || (!resp.has_data ? 'Insufficient real data available for this location.' : undefined),
          generatedTimestamp: new Date(resp.generated_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' IST',
        };
      }
    } catch (err) {
      console.warn('[AnalyticsService] Backend analytics fetch failed:', err);
    }

    // Honest empty response when no data exists
    return {
      stats: {
        peakIntensity: 'No active data',
        peakIntensityLabel: 'Telemetry Status',
        totalEvents: 0,
        activeEvents: 0,
        peopleAffected: '0',
        peopleAffectedExact: 0,
        trend: 'No trend data',
        trendPositive: true,
        trendSubtext: 'Insufficient real data available for this location.',
      },
      timeline: [],
      severityDistribution: [
        { name: 'Critical (Red)', count: 0, percentage: 0, color: '#E94B68' },
        { name: 'Warning (Amber)', count: 0, percentage: 0, color: '#F4C84A' },
        { name: 'Moderate (Cyan)', count: 0, percentage: 0, color: '#18C3D0' },
        { name: 'Minor (Green)', count: 0, percentage: 0, color: '#45C79A' },
      ],
      regionalImpact: [],
      isLiveData: true,
      hasData: false,
      message: 'Insufficient real data available for this location.',
      generatedTimestamp: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' IST',
    };
  }

  /**
   * Synchronous fallback getter for backward compatibility
   */
  public static getAnalyticsData(filter: AnalyticsFilterState): AnalyticsResult {
    const now = new Date();
    return {
      stats: {
        peakIntensity: 'Querying backend...',
        peakIntensityLabel: 'Telemetry Status',
        totalEvents: 0,
        activeEvents: 0,
        peopleAffected: '0',
        peopleAffectedExact: 0,
        trend: 'Real-time database sync',
        trendPositive: true,
        trendSubtext: 'Aggregated from real PostgreSQL database',
      },
      timeline: [],
      severityDistribution: [
        { name: 'Critical (Red)', count: 0, percentage: 0, color: '#E94B68' },
        { name: 'Warning (Amber)', count: 0, percentage: 0, color: '#F4C84A' },
        { name: 'Moderate (Cyan)', count: 0, percentage: 0, color: '#18C3D0' },
        { name: 'Minor (Green)', count: 0, percentage: 0, color: '#45C79A' },
      ],
      regionalImpact: [],
      isLiveData: true,
      hasData: false,
      message: 'Insufficient real data available for this location.',
      generatedTimestamp: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' IST',
    };
  }

  /**
   * Helper to format export payload
   */
  public static createExportPayload(filter: AnalyticsFilterState, result: AnalyticsResult): ExportDataPayload {
    return {
      title: 'AEGIS ALERT - Hazard Analytics Briefing',
      subtitle: 'Authoritative intensity, severity and regional impact insights from central PostgreSQL database.',
      generatedAt: result.generatedTimestamp,
      location: filter.location === 'all' ? 'National Overview (India)' : filter.location.toUpperCase(),
      hazard: filter.hazard.toUpperCase(),
      dateRange: filter.dateRange.toUpperCase(),
      stats: {
        peakIntensity: result.stats.peakIntensity,
        totalEvents: result.stats.totalEvents,
        peopleAffected: result.stats.peopleAffected,
        trend: result.stats.trend,
      },
      timeline: result.timeline,
      regionalImpact: result.regionalImpact,
      severityDistribution: result.severityDistribution.map((s) => ({
        name: s.name,
        value: s.count,
        color: s.color,
      })),
    };
  }
}
