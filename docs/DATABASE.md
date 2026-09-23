# AEGIS Database Schema & PostGIS Reference

## Storage Engine
- **Engine**: PostgreSQL 16 with PostGIS 3.4
- **Spatial Indexing**: GiST indexes on all geography/geometry columns.

## Spatial Proximity Queries
```sql
SELECT id, full_name, role,
       ST_Distance(current_location, ST_SetSRID(ST_MakePoint(:sos_lng, :sos_lat), 4326)::geography) / 1000.0 AS distance_km
FROM users
WHERE role IN ('VOLUNTEER_RESPONDER', 'PRO_RESPONDER')
  AND is_available = TRUE
  AND ST_DWithin(current_location, ST_SetSRID(ST_MakePoint(:sos_lng, :sos_lat), 4326)::geography, 10000)
ORDER BY distance_km ASC
LIMIT 15;
```
