/**
 * AEGIS ALERT - Backend API Response & Schema Types
 * Strict standard JSON schema contract for all endpoints.
 */

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: ApiErrorPayload;
  meta?: {
    timestamp: string;
    requestId?: string;
    version: string;
    pagination?: {
      page: number;
      limit: number;
      total: number;
    };
  };
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: any;
  status: number;
}

export interface UserSession {
  id: string;
  name: string;
  email: string;
  role: 'citizen' | 'official' | 'admin' | 'sdrf_officer';
  phone?: string;
  stateId?: string;
  district?: string;
}

export interface AuthTokenPayload {
  userId: string;
  role: string;
  exp: number;
}

export interface AlertQueryFilter {
  category?: string;
  severity?: string;
  stateId?: string;
  lat?: number;
  lng?: number;
  radiusKm?: number;
  status?: string;
}

export interface IncidentReportSubmission {
  hazardType: string;
  title?: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  location: {
    lat: number;
    lng: number;
    address: string;
    city: string;
    state: string;
    district?: string;
  };
  mediaUrls?: string[];
  contactInfo?: {
    name?: string;
    phone?: string;
    isAnonymous?: boolean;
  };
  casualtiesCount?: number;
  infrastructureDamage?: string;
}
