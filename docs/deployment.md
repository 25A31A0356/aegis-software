# AEGIS Central Data Gateway — Deployment & Operations Guide

Repository: `https://github.com/25A31A0356/aegis-software`

---

## 1. Local Development Setup

### Prerequisites
- Python 3.11+ (Python 3.13 tested and certified)
- Node.js 20+ & npm
- PostgreSQL 16 with PostGIS extension (Automated SQLite fallback enabled for development)
- Redis 7.2 (Automated In-Memory dictionary cache fallback enabled for development)

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/25A31A0356/aegis-software.git
cd "aegis-software"

# Copy example environment configuration
cp .env.example .env
```

### Step 2: Backend Setup
```bash
# Set up Python virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Run full automated test suite (33 tests)
python -m pytest backend/tests

# Launch FastAPI development gateway server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Frontend Admin Console Setup
```bash
# Install frontend dependencies
npm install

# Build production bundle
npm run build

# Start Vite development server
npm run dev
```

The gateway will be accessible at:
- Web Admin / Gateway UI: `http://localhost:5173`
- FastAPI Interactive Swagger Docs: `http://localhost:8000/docs`
- Root Health Probe: `http://localhost:8000/health`
- Gateway Status Matrix: `http://localhost:8000/api/v1/status`

---

## 2. Docker Compose Production Topology

To launch the containerized production stack (PostgreSQL + PostGIS, Redis Cache, FastAPI Central Data Gateway, and Nginx Production Frontend):

```bash
docker compose up -d --build
```

### Service Health Checks
```bash
docker compose ps
```

| Container | Service | Port | Health Check Probe |
| :--- | :--- | :--- | :--- |
| `aegis-postgres` | PostgreSQL 16 + PostGIS | 5432 | `pg_isready -U aegis_user -d aegis_db` |
| `aegis-redis` | Redis In-Memory Cache | 6379 | `redis-cli ping` |
| `aegis-backend` | Central Data Gateway | 8000 | `curl -f http://localhost:8000/health` |
| `aegis-frontend` | Nginx Static Server & Reverse Proxy | 80 / 443 | `curl -f http://localhost/health` |

---

## 3. Database Migration Instructions

### Initial Schema & Extensions
Execute PostgreSQL DDL migrations using `psql` or database orchestration:
```bash
# 1. Base Geospatial & Alert Schema
psql -U aegis_user -d aegis_db -f database/migrations/001_initial_schema.sql

# 2. Central Data Gateway Tables & PostGIS Indexes
psql -U aegis_user -d aegis_db -f database/migrations/002_data_core_schema.sql
```

The application also automatically initializes tables and seeds standard administrative accounts upon startup via `backend/app/database/session.py`.

---

## 4. Production Security Checklist

- [x] **Zero Secret Leakage**: All third-party provider API keys (NASA FIRMS, IMD, CWC, CPCB) exist **strictly in backend `.env`** and encrypted at rest in PostgreSQL with AES-256 Fernet.
- [x] **SSRF Protection**: Outbound HTTP requests to external provider APIs are strictly validated by `SSRFGuard`, prohibiting requests to localhost, loopback (`127.0.0.0/8`), AWS/GCP/Azure instance metadata endpoints (`169.254.169.254`), and private RFC-1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- [x] **Security Headers**: HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block` enforced on all responses.
- [x] **Rate Limiting**: Sliding-window IP rate limiter protects against request storms and downstream provider quota exhaustion.
- [x] **Sanitized Error Responses**: Internal stack traces and file paths are caught by global exception handlers and masked before responding to clients.
- [x] **Client Separation**: `X-Aegis-Client` context differentiates public consumer clients (`web`, `app`) from authenticated administrators (`admin`).

---

## 5. Related Repositories

- **Central Data Gateway (This Repo)**: [https://github.com/25A31A0356/aegis-software](https://github.com/25A31A0356/aegis-software)
- **Aegis Alert Mobile App (Android/iOS)**: [https://github.com/25A31A0356/aegis-alert](https://github.com/25A31A0356/aegis-alert)
- **Aegis Web Portal**: [https://github.com/25A31A0356/Aegis-web](https://github.com/25A31A0356/Aegis-web)
