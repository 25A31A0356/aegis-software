# Multi-stage Dockerfile for AEGIS Unified Data Core Backend
FROM python:3.13-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# Install system dependencies (including curl for healthchecks and libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and configuration under backend package
COPY . /app/backend/

# Create a non-root user for production security
RUN useradd -m -u 1000 aegisuser && \
    chown -R aegisuser:aegisuser /app
USER aegisuser

EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
