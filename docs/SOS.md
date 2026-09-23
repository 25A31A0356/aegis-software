# AEGIS SOS Emergency Lifecycle & Dispatch Architecture

## Rapido-Style Responder Dispatch
1. **Trigger**: Victim activates SOS (3-second safety window).
2. **Persistence**: Durable atomic transaction in PostgreSQL with PostGIS coordinates.
3. **Tier 1 (10 km)**: ST_DWithin search for certified nearby responders; 45s acceptance countdown.
4. **Tier 2 (20 km)**: Automatic radius expansion if unassigned after 45s.
5. **Tier 3 (State Escalation)**: Immediate broadcast to district and state emergency operation centers.
6. **Public Map Visibility**: Expires automatically after 1 hour (`active_map_visibility_until`). Family and assigned responders retain authorized tracking.
