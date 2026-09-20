/**
 * AEGIS ALERT - Central Unified API Client
 * Connects Aegis Web to the unified FastAPI / PostgreSQL backend.
 */

export interface ApiResponseWrapper<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  freshness?: {
    status: string;
    age_seconds: number;
  };
  provenance?: {
    data_type: string;
    source_authority: string;
    processing_version: string;
  };
}

export class ApiClient {
  public static getBaseUrl(version: 'v1' | 'legacy' | 'raw' = 'v1'): string {
    if (typeof window === 'undefined') {
      const envUrl = process?.env?.VITE_API_URL || 'http://127.0.0.1:8000';
      return version === 'v1' ? `${envUrl}/api/v1` : `${envUrl}/api`;
    }
    if (version === 'v1') return '/api/v1';
    if (version === 'raw') return '';
    return '/api';
  }

  private static getAuthHeader(): Record<string, string> {
    if (typeof localStorage === 'undefined') return {};
    const token =
      localStorage.getItem('aegis_auth_token') ||
      localStorage.getItem('agies_auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  public static async get<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined | null>,
    version: 'v1' | 'legacy' | 'raw' = 'v1'
  ): Promise<T | null> {
    try {
      let url = `${this.getBaseUrl(version)}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
      if (params) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, val]) => {
          if (val !== undefined && val !== null) searchParams.append(key, String(val));
        });
        const qs = searchParams.toString();
        if (qs) url += `${url.includes('?') ? '&' : '?'}${qs}`;
      }

      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...this.getAuthHeader(),
        },
      });

      if (!res.ok) {
        console.warn(`[ApiClient] GET ${url} returned ${res.status}`);
        return null;
      }

      const json = await res.json();
      if (json && typeof json === 'object' && 'data' in json) {
        return json.data as T;
      }
      return json as T;
    } catch (err) {
      console.warn(`[ApiClient] Network request failed for GET ${endpoint}:`, err);
      return null;
    }
  }

  public static async post<T, B = any>(
    endpoint: string,
    body: B,
    version: 'v1' | 'legacy' | 'raw' = 'v1'
  ): Promise<T | null> {
    try {
      const url = `${this.getBaseUrl(version)}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...this.getAuthHeader(),
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const errMsg = errJson?.error?.message || errJson?.detail || `HTTP ${res.status}`;
        console.warn(`[ApiClient] POST ${url} returned ${res.status}: ${errMsg}`);
        throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg));
      }

      const json = await res.json();
      if (json && typeof json === 'object' && 'data' in json) {
        return json.data as T;
      }
      return json as T;
    } catch (err) {
      console.warn(`[ApiClient] Network error on POST ${endpoint}:`, err);
      throw err;
    }
  }

  public static async put<T, B = any>(
    endpoint: string,
    body: B,
    version: 'v1' | 'legacy' | 'raw' = 'v1'
  ): Promise<T | null> {
    try {
      const url = `${this.getBaseUrl(version)}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
      const res = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...this.getAuthHeader(),
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) return null;
      const json = await res.json();
      if (json && typeof json === 'object' && 'data' in json) {
        return json.data as T;
      }
      return json as T;
    } catch (err) {
      console.warn(`[ApiClient] Network error on PUT ${endpoint}:`, err);
      return null;
    }
  }

  public static async delete<T>(
    endpoint: string,
    version: 'v1' | 'legacy' | 'raw' = 'v1'
  ): Promise<T | null> {
    try {
      const url = `${this.getBaseUrl(version)}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
      const res = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...this.getAuthHeader(),
        },
      });

      if (!res.ok) return null;
      const json = await res.json();
      if (json && typeof json === 'object' && 'data' in json) {
        return json.data as T;
      }
      return json as T;
    } catch (err) {
      console.warn(`[ApiClient] Network error on DELETE ${endpoint}:`, err);
      return null;
    }
  }
}
