# ADR 003: Realtime Communication Architecture (SSE + WebSocket Fallback)
**Status:** Approved (Phase 0 Baseline)  
**Date:** 2026-09-21  
**Decider Hat:** Full-Stack + Realtime Engineer

---

## Context
When an SOS is activated or a disaster warning is issued, web dashboards and active mobile clients must receive updates within < 2 seconds. However, network conditions in disaster zones may be severely degraded.

## Decision
1. **Primary Stream**: **Server-Sent Events (SSE)** via `GET /api/v1/events` for lightweight, one-way event streaming to web and mobile clients (efficient over cellular networks and HTTP/2 proxies).
2. **Bidirectional Channel**: **WebSocket** via `/api/v1/ws` for interactive responder-dispatcher communication.
3. **Authoritative State via REST**: Realtime is an optimization. If the realtime connection drops, clients automatically fetch authoritative state via `GET /api/v1/sos/active` with monotonic timestamp cursors.

## Consequences
- Eliminates connection storms; ensures reliable fallback under weak network conditions.
