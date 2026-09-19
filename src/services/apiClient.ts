/**
 * AEGIS ALERT - Frontend API Client
 * Typed service connector linking the frontend to backend API routes with graceful fallback.
 */

import { ApiResponse } from '../../server/types/api';

export class ApiClient {
  private static getBaseUrl(version: 'v1' | 'legacy' | 'raw' = 'legacy'): string {
    if (typeof window === 'undefined') {
      return version === 'v1' ? 'http://localhost:8000/api/v1' : 'http://localhost:5173/api';
    }
    if (version === 'v1') return '/api/v1';
    if (version === 'raw') return '';
    return '/api';
  }

  private static getAuthHeader(): Record<string, string> {
    const token =
      typeof localStorage !== 'undefined'
        ? localStorage.getItem('aegis_auth_token') || localStorage.getItem('agies_auth_token')
        : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  public static async get<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined>,
    version: 'v1' | 'legacy' | 'raw' = 'legacy'
  ): Promise<T | null> {
    try {
      let url = `${this.getBaseUrl(version)}${endpoint}`;
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
          ...this.getAuthHeader(),
        },
      });

      if (!res.ok) {
        console.warn(`[ApiClient] GET ${endpoint} responded with status ${res.status}`);
        return null;
      }

      const json = await res.json();
      if (version === 'v1') {
        // FastAPI returns directly or in standard structure
        return (json && json.data !== undefined ? json.data : json) as T;
      }
      const legacyResp: ApiResponse<T> = json;
      return legacyResp.success && legacyResp.data ? legacyResp.data : null;
    } catch (err) {
      console.warn(`[ApiClient] Network request failed for GET ${endpoint}:`, err);
      return null;
    }
  }

  public static async post<T, B = any>(
    endpoint: string,
    body: B,
    version: 'v1' | 'legacy' | 'raw' = 'legacy'
  ): Promise<T | null> {
    try {
      const url = `${this.getBaseUrl(version)}${endpoint}`;
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeader(),
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        console.warn(`[ApiClient] POST ${endpoint} responded with status ${res.status}`);
        const errJson = await res.json().catch(() => null);
        if (errJson && errJson.detail) {
          throw new Error(typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail));
        }
        return null;
      }

      const json = await res.json();
      if (version === 'v1') {
        return (json && json.data !== undefined ? json.data : json) as T;
      }
      const legacyResp: ApiResponse<T> = json;
      return legacyResp.success && legacyResp.data ? legacyResp.data : null;
    } catch (err) {
      console.warn(`[ApiClient] Network request failed for POST ${endpoint}:`, err);
      throw err;
    }
  }

  public static async put<T, B = any>(
    endpoint: string,
    body: B,
    version: 'v1' | 'legacy' | 'raw' = 'legacy'
  ): Promise<T | null> {
    try {
      const url = `${this.getBaseUrl(version)}${endpoint}`;
      const res = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeader(),
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) return null;
      const json = await res.json();
      return (version === 'v1' ? (json.data !== undefined ? json.data : json) : json.data) as T;
    } catch (err) {
      return null;
    }
  }

  public static async delete<T>(
    endpoint: string,
    version: 'v1' | 'legacy' | 'raw' = 'legacy'
  ): Promise<T | null> {
    try {
      const url = `${this.getBaseUrl(version)}${endpoint}`;
      const res = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeader(),
        },
      });

      if (!res.ok) {
        return null;
      }

      const json = await res.json();
      if (version === 'v1') {
        return (json && json.data !== undefined ? json.data : json) as T;
      }
      const legacyResp: ApiResponse<T> = json;
      return legacyResp.success && legacyResp.data ? legacyResp.data : null;
    } catch (err) {
      return null;
    }
  }
}
