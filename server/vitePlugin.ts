/**
 * AEGIS ALERT - Vite Backend Middleware Plugin
 * Connects the real backend router / FastAPI proxy to the Vite development and preview server.
 */

import { Plugin } from 'vite';
import { handleBackendApiRequest, HttpRequestContext } from './router';

export function aegisBackendPlugin(): Plugin {
  return {
    name: 'aegis-alert-backend',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const urlStr = req.url || '';
        const [path, queryString] = urlStr.split('?');

        if (!path.startsWith('/api')) {
          return next();
        }

        // Parse query string
        const query: Record<string, string> = {};
        if (queryString) {
          const params = new URLSearchParams(queryString);
          params.forEach((val, key) => {
            query[key] = val;
          });
        }

        // Parse request body for POST/PUT/PATCH/DELETE
        let body: any = undefined;
        if (req.method === 'POST' || req.method === 'PUT' || req.method === 'PATCH' || req.method === 'DELETE') {
          body = await new Promise((resolve) => {
            let data = '';
            req.on('data', (chunk) => {
              data += chunk;
            });
            req.on('end', () => {
              try {
                resolve(data ? JSON.parse(data) : undefined);
              } catch {
                resolve(data);
              }
            });
          });
        }

        // First: Attempt to forward request to real FastAPI Data Core backend at http://127.0.0.1:8000
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 2000);
          
          let fetchBody: any = undefined;
          if (body !== undefined && req.method !== 'GET' && req.method !== 'HEAD') {
            fetchBody = typeof body === 'string' ? body : JSON.stringify(body);
          }

          const backendHost = process.env.BACKEND_URL || process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
          const fastApiUrl = `${backendHost}${urlStr}`;
          const forwardHeaders: Record<string, string> = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          };
          if (req.headers['authorization']) {
            forwardHeaders['authorization'] = req.headers['authorization'] as string;
          }
          if (req.headers['x-aegis-user-id']) {
            forwardHeaders['x-aegis-user-id'] = req.headers['x-aegis-user-id'] as string;
          }

          const fastApiResp = await fetch(fastApiUrl, {
            method: req.method || 'GET',
            headers: forwardHeaders,
            body: fetchBody,
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (fastApiResp) {
            res.statusCode = fastApiResp.status;
            fastApiResp.headers.forEach((value, key) => {
              if (key.toLowerCase() !== 'content-encoding') {
                res.setHeader(key, value);
              }
            });
            const respText = await fastApiResp.text();
            res.end(respText);
            return;
          }
        } catch (_fastApiErr) {
          // FastAPI backend is offline or timed out -> proceed to local router fallback
        }

        // Fallback: Use built-in TypeScript Router
        const httpContext: HttpRequestContext = {
          method: req.method || 'GET',
          url: urlStr,
          path,
          query,
          headers: req.headers as any,
          body,
          clientIp: (req.headers['x-forwarded-for'] as string) || req.socket.remoteAddress,
        };

        try {
          const response = await handleBackendApiRequest(httpContext);

          res.statusCode = response.status;
          for (const [key, value] of Object.entries(response.headers)) {
            res.setHeader(key, value);
          }

          if (response.status === 204 || response.body === '' || response.body === undefined) {
            res.end();
          } else {
            res.end(typeof response.body === 'string' ? response.body : JSON.stringify(response.body));
          }
        } catch (pluginErr) {
          console.error('[Vite Backend Middleware Plugin Exception]', pluginErr);
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({
            success: false,
            error: {
              code: 'INTERNAL_SERVER_ERROR',
              message: 'An unexpected error occurred while processing the request.',
              status: 500
            }
          }));
        }
      });
    },
  };
}

export const agiesBackendPlugin = aegisBackendPlugin;
