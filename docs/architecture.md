# AEGIS Master Architecture Blueprint

## System Overview
AEGIS ALERT is a mission-critical, multi-hazard disaster intelligence and emergency response platform built on a hardened layered architecture:

```
[Mobile App: Expo React Native]      [Web Portal: React 18 + Vite]
                  |                              |
                  +---------------+--------------+
                                  |
                           [CloudFront / WAF]
                                  |
                      [Application Load Balancer]
                                  |
                      [FastAPI Master Cluster]
                                  |
             +--------------------+--------------------+
             |                    |                    |
     [PostgreSQL + PostGIS] [Redis Cluster] [Worker Subsystems]
             |                    |                    |
             +--------------------+--------------------+
```

## Layered Domains
1. **Core API**: FastAPI async runtime with strict Pydantic validation, JWT RBAC, and rate limits.
2. **Ingestion Engine**: Modular adapters for IMD, CWC, CPCB, INCOIS, USGS, NASA FIRMS, and Open-Meteo.
3. **Decoupled Risk Engine**: Separates physical Environmental Risk (0–100) from Civilian Incident Load and Emergency Response Load.
4. **Dual Map GIS**: Map 1 (Weather & Multi-Hazard Intelligence) vs. Map 2 (Tactical SOS Command Map with 1-hour auto-expiration).
5. **Offline Emergency Fallback**: Multi-tier priority: Online HTTPS -> Native SMS -> Direct 112 Voice -> Local SQLite Queue.
