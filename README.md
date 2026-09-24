# 🛡️ AEGIS ALERT — Central Backend & Server Engine

**`aegis-software`** is the core server, API gateway, ingestion, and machine learning engine for the AEGIS ALERT platform.

## 🚀 Key Modules
- **`backend/app/api/`**: FastAPI REST & WebSocket endpoints (`/api/v1/weather`, `/api/v1/sos`, `/api/v1/correlation/decoupled-risk`, `/api/v1/hazards`).
- **`backend/app/ingestion/`**: Real-time telemetry adapters (IMD, CWC, CPCB, INCOIS, USGS, NASA FIRMS, Open-Meteo).
- **`backend/app/ml/`**: Numerical feature correlation, uncertainty bounds, and model registry.
- **`backend/app/realtime/`**: Redis Streams & WebSocket distress event bus.
- **`backend/app/dispatch/`**: Rapido-style 10km/20km spatial responder matching via PostGIS.

## 🛠️ Quickstart
```bash
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
