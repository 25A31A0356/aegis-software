# AEGIS Unified Data Core — Deployment & Operations Guide

## 1. Local Development Setup

### Prerequisites
- Python 3.11+ (Python 3.13 tested)
- Node.js 20+ & npm
- PostgreSQL 16 with PostGIS (optional for local SQLite fallback)
- Redis 7.2 (optional for local in-memory fallback)

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/25A31A0356/Aegis-web.git
cd "Aegis software"

# Create .env from template
cp .env.example .env
```

### Step 2: Backend Setup
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Run tests
pytest tests/

# Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Frontend Setup
```bash
# In project root:
npm install
npm run dev
```

The web application will be available at `http://localhost:5173`, with the backend API listening at `http://localhost:8000/api/v1/`.

---

## 2. Docker & Docker Compose Deployment (Production)

To launch the full production topology (PostgreSQL + PostGIS, Redis, FastAPI Backend, and Nginx React Frontend):

```bash
docker compose up -d --build
```

### Verify Container Health
```bash
docker compose ps
```

All 4 services (`aegis-postgres`, `aegis-redis`, `aegis-backend`, `aegis-frontend`) will report `healthy`.

---

## 3. Production Hardening Checklist

1. **Rotate Cryptographic Keys**:
   - Generate a unique 32-byte url-safe base64 Fernet key for `ENCRYPTION_KEY`.
   - Set a strong, random 64-character secret for `JWT_SECRET_KEY`.
2. **Configure Domain & TLS Certificates**:
   - Terminate SSL/TLS via reverse proxy (Cloudflare, Nginx, or AWS ALB) with HSTS enabled.
3. **Set Up PostgreSQL Backups**:
   - Enable continuous WAL archiving or daily automated `pg_dump` snapshots.
4. **Tune Worker Concurrency**:
   - Set `WORKERS = 2 * CPU_CORES + 1` in `backend/Dockerfile` for high-throughput deployments.
