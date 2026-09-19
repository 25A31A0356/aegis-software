/**
 * AEGIS UNIFIED DATA CORE - Frontend Service
 * Connects the React application to the FastAPI Unified Data Core endpoints (/api/v1/...)
 */

import { ApiClient } from './apiClient';

export interface DataSourceDTO {
  id: string;
  name: string;
  code: string;
  hazard_type: string;
  base_url: string;
  auth_type: string;
  is_active: boolean;
  ingestion_interval_seconds: number;
  last_polled_at?: string;
  last_success_at?: string;
  last_error?: string;
  consecutive_failures: number;
  total_records_ingested: number;
  masked_key?: string;
  created_at?: string;
  updated_at?: string;
}

export interface DataSourceCreateRequest {
  name: string;
  code: string;
  hazard_type: string;
  base_url: string;
  auth_type?: string;
  api_key?: string;
  headers_json?: Record<string, string>;
  is_active?: boolean;
  ingestion_interval_seconds?: number;
  verify_ssl?: boolean;
}

export interface FieldMappingDTO {
  id?: string;
  source_id: string;
  source_field_path: string;
  standard_field_name: string;
  data_type: string;
  source_unit?: string;
  target_unit?: string;
  transformation_rule?: string;
  is_required: boolean;
  confidence_score?: number;
}

export interface IngestionTestRequest {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  auth_header_value?: string;
  timeout_seconds?: number;
}

export interface IngestionTestResponse {
  success: boolean;
  status_code?: number;
  latency_ms: number;
  detected_hazard?: string;
  is_ssrf_safe: boolean;
  sample_data_count: number;
  detected_fields: Array<{
    field_path: string;
    sample_value: any;
    data_type: string;
    suggested_target: string;
    suggested_unit?: string;
    confidence: number;
  }>;
  raw_preview: any;
  error?: string;
}

export interface NormalizedObservationDTO {
  id: string;
  source_id: string;
  hazard_type: string;
  external_id?: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  elevation_m?: number;
  timestamp: string;
  temperature_c?: number;
  humidity_percent?: number;
  pressure_hpa?: number;
  wind_speed_kmh?: number;
  wind_direction_deg?: number;
  precipitation_mm?: number;
  water_level_m?: number;
  flow_rate_cumecs?: number;
  flood_stage?: string;
  magnitude?: number;
  depth_km?: number;
  intensity?: string;
  pm25?: number;
  pm10?: number;
  aqi?: number;
  fire_radiative_power?: number;
  confidence_score?: number;
  is_validated: boolean;
  data_type?: 'RAW_OBSERVATION' | 'NORMALIZED_OBSERVATION' | 'AI_GENERATED';
  raw_payload?: any;
}

export interface CorrelationResultDTO {
  latitude: number;
  longitude: number;
  radius_km: number;
  composite_risk_score: number;
  threat_level: string;
  active_hazards: string[];
  correlated_event_count: number;
  multi_hazard_events: any[];
  safety_recommendations: string[];
  last_updated: string;
}

export interface SystemStatsDTO {
  total_sources: number;
  active_sources: number;
  total_raw_observations: number;
  total_normalized_observations: number;
  total_active_alerts: number;
  recent_24h_ingestions: number;
  database_status: string;
  redis_cache_status: string;
  cache_hit_rate_pct: number;
  system_uptime_seconds: number;
}

export interface AuditLogDTO {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  actor_id?: string;
  client_ip?: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface ProcessingJobDTO {
  id: string;
  source_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  records_fetched: number;
  records_normalized: number;
  records_validated: number;
  records_deduplicated: number;
  error_message?: string;
  duration_ms: number;
  started_at: string;
  completed_at?: string;
}

export class DataCoreService {
  /**
   * Fetch system health & component telemetry
   */
  public static async getHealth(): Promise<any> {
    return ApiClient.get('/health', undefined, 'v1');
  }

  /**
   * Fetch unified administrative statistics
   */
  public static async getStats(): Promise<SystemStatsDTO | null> {
    return ApiClient.get<SystemStatsDTO>('/admin/stats', undefined, 'v1');
  }

  /**
   * List all registered data sources with masked keys
   */
  public static async getDataSources(): Promise<DataSourceDTO[]> {
    const res = await ApiClient.get<DataSourceDTO[]>('/sources', undefined, 'v1');
    return res || [];
  }

  /**
   * Register a new external data source
   */
  public static async createDataSource(data: DataSourceCreateRequest): Promise<DataSourceDTO | null> {
    return ApiClient.post<DataSourceDTO>('/sources', data, 'v1');
  }

  /**
   * Manually trigger immediate ingestion for a data source
   */
  public static async triggerIngestion(sourceId: string): Promise<any> {
    return ApiClient.post(`/sources/${sourceId}/trigger`, {}, 'v1');
  }

  /**
   * Test an arbitrary endpoint for SSRF safety, field detection, and normalization
   */
  public static async testEndpoint(params: IngestionTestRequest): Promise<IngestionTestResponse | null> {
    return ApiClient.post<IngestionTestResponse>('/sources/test', params, 'v1');
  }

  /**
   * Fetch field mappings for a specific source
   */
  public static async getFieldMappings(sourceId: string): Promise<FieldMappingDTO[]> {
    const res = await ApiClient.get<FieldMappingDTO[]>(`/sources/${sourceId}/mappings`, undefined, 'v1');
    return res || [];
  }

  /**
   * Save or update field mappings for a data source
   */
  public static async saveFieldMappings(sourceId: string, mappings: FieldMappingDTO[]): Promise<FieldMappingDTO[]> {
    const res = await ApiClient.post<FieldMappingDTO[]>(`/sources/${sourceId}/mappings`, { mappings }, 'v1');
    return res || [];
  }

  /**
   * Fetch normalized observations across multi-hazard categories
   */
  public static async getObservations(params?: {
    hazard_type?: string;
    min_lat?: number;
    max_lat?: number;
    min_lon?: number;
    max_lon?: number;
    limit?: number;
  }): Promise<NormalizedObservationDTO[]> {
    const res = await ApiClient.get<NormalizedObservationDTO[]>('/hazards/observations', params, 'v1');
    return res || [];
  }

  /**
   * Fetch spatial-temporal correlation analysis
   */
  public static async getCorrelation(lat: number, lon: number, radiusKm: number = 50): Promise<CorrelationResultDTO | null> {
    return ApiClient.get<CorrelationResultDTO>('/correlation', { lat, lon, radius_km: radiusKm }, 'v1');
  }

  /**
   * Fetch security audit logs
   */
  public static async getAuditLogs(limit: number = 50): Promise<AuditLogDTO[]> {
    const res = await ApiClient.get<AuditLogDTO[]>('/admin/audit-logs', { limit }, 'v1');
    return res || [];
  }

  /**
   * Fetch background ingestion job runs
   */
  public static async getProcessingJobs(limit: number = 50): Promise<ProcessingJobDTO[]> {
    const res = await ApiClient.get<ProcessingJobDTO[]>('/admin/jobs', { limit }, 'v1');
    return res || [];
  }
}
