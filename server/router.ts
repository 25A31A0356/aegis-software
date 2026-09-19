/**
 * AEGIS ALERT - Unified Backend Request Router
 * Dispatches all REST endpoints with rate limiting, auth checks, schema validation, and proper HTTP status codes.
 */

import { RateLimiter } from './middleware/rateLimiter';
import { AuthMiddleware } from './middleware/authMiddleware';
import { ValidationMiddleware, ErrorHandler } from './middleware/validationMiddleware';
import { SecurityMiddleware } from './middleware/securityMiddleware';
import { SanitizationMiddleware } from './middleware/sanitizationMiddleware';
import { AuditLogger } from './services/AuditLogger';
import { AuthService } from './services/AuthService';
import { WeatherService } from './services/WeatherService';
import { AlertService } from './services/AlertService';
import { RiskService } from './services/RiskService';
import { AnalyticsService } from './services/AnalyticsService';
import { ReportService } from './services/ReportService';
import { LocationService } from './services/LocationService';
import { MapService } from './services/MapService';
import { AIService } from './services/AIService';
import { NotificationService } from './services/NotificationService';
import { SAFETY_GUIDES } from '../src/data/safetyGuidesData';

export interface HttpRequestContext {
  method: string;
  url: string;
  path: string;
  query: Record<string, string>;
  headers: Record<string, string | string[] | undefined>;
  body?: any;
  clientIp?: string;
}

export interface HttpResponseContext {
  status: number;
  headers: Record<string, string>;
  body: any;
}

export async function handleBackendApiRequest(req: HttpRequestContext): Promise<HttpResponseContext> {
  const { method, path, query, headers, body } = req;
  const clientIp = req.clientIp || (headers['x-forwarded-for'] as string) || '127.0.0.1';
  const origin = (headers['origin'] as string) || (headers['host'] ? `http://${headers['host']}` : undefined);
  const baseSecurityHeaders = SecurityMiddleware.getSecurityHeaders(origin);

  // 1. CORS Preflight OPTIONS Handling
  if (method === 'OPTIONS') {
    return {
      status: 204,
      headers: {
        ...baseSecurityHeaders,
        'Content-Type': 'application/json',
      },
      body: '',
    };
  }

  // 2. Sliding Window Endpoint Rate Limiting
  const rateLimit = RateLimiter.check(clientIp, path);
  if (!rateLimit.allowed) {
    AuditLogger.log({
      action: 'RATE_LIMIT_BLOCKED',
      severity: 'WARN',
      clientIp,
      details: { path, limit: rateLimit.limit },
    });

    const err = ErrorHandler.createError(
      'RATE_LIMIT_EXCEEDED',
      'Too many requests sent to the emergency intelligence API. Please wait a moment before trying again.',
      429,
      { resetTime: new Date(rateLimit.resetTime).toISOString() }
    );
    return {
      status: err.status,
      headers: {
        ...baseSecurityHeaders,
        'Content-Type': 'application/json',
        'X-RateLimit-Limit': rateLimit.limit.toString(),
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': rateLimit.resetTime.toString(),
      },
      body: err.body,
    };
  }

  // 3. Extract and Verify Authentication Context
  const authHeader = (headers['authorization'] as string) || undefined;
  const auth = AuthMiddleware.authenticate(authHeader, clientIp);

  // Attach rate limit and security headers helper
  const attachHeaders = (customHeaders?: Record<string, string>): Record<string, string> => ({
    ...baseSecurityHeaders,
    'Content-Type': 'application/json',
    'X-RateLimit-Limit': rateLimit.limit.toString(),
    'X-RateLimit-Remaining': rateLimit.remaining.toString(),
    'X-RateLimit-Reset': rateLimit.resetTime.toString(),
    ...(customHeaders || {}),
  });

  try {
    // -------------------------------------------------------------
    // GET /api/csrf-token
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/csrf-token') {
      const csrfToken = SecurityMiddleware.generateCsrfToken(clientIp);
      const res = ErrorHandler.createResponse({ csrfToken });
      return {
        status: res.status,
        headers: attachHeaders({
          'Set-Cookie': SecurityMiddleware.getSecureCookieString('aegis_csrf', csrfToken, 14400),
        }),
        body: res.body,
      };
    }

    // -------------------------------------------------------------
    // POST /api/auth/login
    // -------------------------------------------------------------
    if (method === 'POST' && path === '/api/auth/login') {
      const sanitized = SanitizationMiddleware.sanitizeObject(body || {});
      if (sanitized.hasSecurityThreat) {
        const err = ErrorHandler.createError('SECURITY_VIOLATION', 'Invalid characters in login payload.', 400);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const loginResult = await AuthService.login(sanitized.sanitized);
      AuditLogger.log({
        action: 'USER_LOGIN_SUCCESS',
        severity: 'INFO',
        clientIp,
        userId: loginResult.user.id,
        userRole: loginResult.user.role,
        details: { email: loginResult.user.email },
      });

      const res = ErrorHandler.createResponse(loginResult);
      return {
        status: res.status,
        headers: attachHeaders({
          'Set-Cookie': SecurityMiddleware.getSecureCookieString('aegis_session', loginResult.token, 86400),
        }),
        body: res.body,
      };
    }

    // -------------------------------------------------------------
    // GET /api/auth/me
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/auth/me') {
      if (!auth.isAuthenticated || !auth.user) {
        const err = ErrorHandler.createError('UNAUTHORIZED', 'Missing or invalid authentication token.', 401);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }
      const res = ErrorHandler.createResponse({ user: auth.user, isAuthenticated: true });
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/admin/audit-logs (Protected: Official & Admin Only)
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/admin/audit-logs') {
      if (!auth.isAuthenticated || !auth.user) {
        const err = ErrorHandler.createError('UNAUTHORIZED', 'Authentication required to access audit logs.', 401);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const isAuthorized = AuthMiddleware.authorizeRole(auth, ['admin', 'official', 'sdrf_officer']);
      if (!isAuthorized) {
        AuditLogger.log({
          action: 'RBAC_ACCESS_DENIED',
          severity: 'SECURITY_ALERT',
          clientIp,
          userId: auth.user.id,
          userRole: auth.user.role,
          details: { endpoint: '/api/admin/audit-logs', requiredRole: 'admin/official' },
        });

        const err = ErrorHandler.createError('FORBIDDEN', 'Access denied. Insufficient administrative privileges.', 403);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const logs = AuditLogger.getLogs({
        severity: query.severity as any,
        action: query.action,
        limit: query.limit ? parseInt(query.limit, 10) : 50,
      });

      const res = ErrorHandler.createResponse({ logs, total: logs.length });
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/admin/system-status (Protected: Admin Only)
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/admin/system-status') {
      if (!auth.isAuthenticated || !auth.user) {
        const err = ErrorHandler.createError('UNAUTHORIZED', 'Authentication required for system status.', 401);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      if (!AuthMiddleware.authorizeRole(auth, ['admin'])) {
        const err = ErrorHandler.createError('FORBIDDEN', 'Access restricted to system administrators.', 403);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const statusData = {
        serverTime: new Date().toISOString(),
        securityPosture: 'HARDENED',
        rateLimiting: 'ACTIVE',
        corsPolicy: 'STRICT',
        postgisStatus: 'HEALTHY',
        activeAlertsCount: 14,
        auditLogsCount: AuditLogger.getLogs().length,
      };

      const res = ErrorHandler.createResponse(statusData);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/alerts
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/alerts') {
      const alerts = await AlertService.getAlerts({
        category: query.category ? SanitizationMiddleware.stripHtmlTags(query.category) : undefined,
        severity: query.severity ? SanitizationMiddleware.stripHtmlTags(query.severity) : undefined,
        stateId: query.stateId ? SanitizationMiddleware.stripHtmlTags(query.stateId) : undefined,
      });
      const res = ErrorHandler.createResponse(alerts);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/alerts/nearby
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/alerts/nearby') {
      const lat = parseFloat(query.lat || '19.0760');
      const lng = parseFloat(query.lng || '72.8777');
      const radiusKm = parseFloat(query.radiusKm || '100');

      if (isNaN(lat) || isNaN(lng) || !SanitizationMiddleware.validateCoordinates(lat, lng)) {
        const err = ErrorHandler.createError('INVALID_COORDINATES', 'Valid latitude (-90 to 90) and longitude (-180 to 180) are required.', 400);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const alerts = await AlertService.getNearbyAlerts(lat, lng, radiusKm);
      const res = ErrorHandler.createResponse(alerts);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/weather
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/weather') {
      const lat = query.lat ? parseFloat(query.lat) : undefined;
      const lng = query.lng ? parseFloat(query.lng) : undefined;
      const city = query.city ? SanitizationMiddleware.stripHtmlTags(query.city) : undefined;

      if (lat !== undefined && lng !== undefined && !SanitizationMiddleware.validateCoordinates(lat, lng)) {
        const err = ErrorHandler.createError('INVALID_COORDINATES', 'Supplied coordinates are out of valid bounds.', 400);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const weather = await WeatherService.getWeather(lat, lng, city);
      const res = ErrorHandler.createResponse(weather);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/risk
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/risk') {
      const lat = query.lat ? parseFloat(query.lat) : undefined;
      const lng = query.lng ? parseFloat(query.lng) : undefined;
      const stateId = query.stateId ? SanitizationMiddleware.stripHtmlTags(query.stateId) : undefined;

      if (lat !== undefined && lng !== undefined && !SanitizationMiddleware.validateCoordinates(lat, lng)) {
        const err = ErrorHandler.createError('INVALID_COORDINATES', 'Supplied coordinates are out of valid bounds.', 400);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const risk = await RiskService.evaluateRisk(lat, lng, stateId);
      const res = ErrorHandler.createResponse(risk);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/hazards
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/hazards') {
      const alerts = await AlertService.getAlerts();
      const res = ErrorHandler.createResponse(alerts);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/safety-guides
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/safety-guides') {
      const slug = query.slug ? SanitizationMiddleware.stripHtmlTags(query.slug) : undefined;
      if (slug && SAFETY_GUIDES[slug]) {
        const res = ErrorHandler.createResponse(SAFETY_GUIDES[slug]);
        return { status: res.status, headers: attachHeaders(), body: res.body };
      }
      const res = ErrorHandler.createResponse(Object.values(SAFETY_GUIDES));
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/analytics
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/analytics') {
      const location = query.location ? SanitizationMiddleware.stripHtmlTags(query.location) : undefined;
      const hazard = query.hazard ? SanitizationMiddleware.stripHtmlTags(query.hazard) : undefined;
      const dateRange = query.dateRange ? SanitizationMiddleware.stripHtmlTags(query.dateRange) : undefined;

      const analytics = await AnalyticsService.getAnalytics({ location, hazard, dateRange });
      const res = ErrorHandler.createResponse(analytics);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/map/events
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/map/events') {
      const lat = query.lat ? parseFloat(query.lat) : undefined;
      const lng = query.lng ? parseFloat(query.lng) : undefined;
      const events = await MapService.getMapEvents(lat, lng);
      const res = ErrorHandler.createResponse(events);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/map/layers
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/map/layers') {
      const lat = query.lat ? parseFloat(query.lat) : undefined;
      const lng = query.lng ? parseFloat(query.lng) : undefined;
      const layers = await MapService.getMapLayers(lat, lng);
      const res = ErrorHandler.createResponse(layers);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // GET /api/locations
    // -------------------------------------------------------------
    if (method === 'GET' && path === '/api/locations') {
      const locations = await LocationService.getSavedLocations();
      const res = ErrorHandler.createResponse(locations);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // POST /api/locations
    // -------------------------------------------------------------
    if (method === 'POST' && path === '/api/locations') {
      const validation = ValidationMiddleware.validateLocationCreation(body);
      if (!validation.valid) {
        const err = ErrorHandler.createError('VALIDATION_ERROR', 'Invalid location payload.', 400, validation.errors);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const added = await LocationService.addSavedLocation(validation.sanitizedBody);
      const res = ErrorHandler.createResponse(added, 201);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // DELETE /api/locations/:id
    // -------------------------------------------------------------
    if (method === 'DELETE' && path.startsWith('/api/locations/')) {
      const id = SanitizationMiddleware.stripHtmlTags(path.replace('/api/locations/', ''));
      const deleted = await LocationService.deleteSavedLocation(id);
      if (!deleted) {
        const err = ErrorHandler.createError('NOT_FOUND', `Saved location "${id}" was not found.`, 404);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }
      const res = ErrorHandler.createResponse({ id, deleted: true });
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // POST /api/reports
    // -------------------------------------------------------------
    if (method === 'POST' && path === '/api/reports') {
      const validation = ValidationMiddleware.validateReportSubmission(body);
      if (!validation.valid) {
        const err = ErrorHandler.createError('VALIDATION_ERROR', 'Invalid incident report submission.', 400, validation.errors);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const created = await ReportService.createReport(validation.sanitizedBody, clientIp);
      const res = ErrorHandler.createResponse(created, 201);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // -------------------------------------------------------------
    // POST /api/reports/media (Strict Server-Side Validation)
    // -------------------------------------------------------------
    if (method === 'POST' && path === '/api/reports/media') {
      if (!body || !body.fileName) {
        const err = ErrorHandler.createError('BAD_REQUEST', 'fileName is required for media upload.', 400);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      try {
        const uploaded = await ReportService.processMediaUpload(body, clientIp);
        const res = ErrorHandler.createResponse(uploaded, 201);
        return { status: res.status, headers: attachHeaders(), body: res.body };
      } catch (uploadErr: any) {
        const err = ErrorHandler.createError('FILE_REJECTED', uploadErr.message || 'File upload rejected by security filter.', 400);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }
    }

    // -------------------------------------------------------------
    // POST /api/ai/chat
    // -------------------------------------------------------------
    if (method === 'POST' && path === '/api/ai/chat') {
      const validation = ValidationMiddleware.validateAIChatRequest(body);
      if (!validation.valid) {
        const err = ErrorHandler.createError('VALIDATION_ERROR', 'Invalid AI chat request format.', 400, validation.errors);
        return { status: err.status, headers: attachHeaders(), body: err.body };
      }

      const aiResponse = await AIService.processMessage(validation.sanitizedBody);
      const res = ErrorHandler.createResponse(aiResponse);
      return { status: res.status, headers: attachHeaders(), body: res.body };
    }

    // Route Not Found (404)
    const notFoundErr = ErrorHandler.createError(
      'ROUTE_NOT_FOUND',
      `The requested endpoint ${method} ${path} does not exist on AEGIS ALERT backend.`,
      404
    );
    return { status: notFoundErr.status, headers: attachHeaders(), body: notFoundErr.body };
  } catch (serverErr: any) {
    console.error('[AEGIS Backend Error]', serverErr);
    // Redact stack traces and internal secrets from error response
    const internalErr = ErrorHandler.createError(
      'INTERNAL_SERVER_ERROR',
      'An unexpected error occurred while processing emergency intelligence.',
      500
    );
    return { status: internalErr.status, headers: attachHeaders(), body: internalErr.body };
  }
}
