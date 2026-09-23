"""
AEGIS UNIFIED DATA CORE - Main FastAPI Application
Production-Ready Real-Time Weather & Multi-Hazard Data Infrastructure
Enhanced with Phase 1 Global Request Tracking & Standard Error Envelopes
"""
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.database.session import init_db, get_db
from backend.app.scheduler.job_scheduler import start_scheduler, stop_scheduler, sync_scheduler_jobs
from backend.app.api.v1.router import api_router
from backend.app.api.v1.trpc_compat import router as trpc_router
from backend.app.api.v1.health import check_overall_health
from backend.app.core.exceptions import AegisCoreException
from backend.app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]...")
    await init_db()
    if settings.ENABLE_BACKGROUND_SCHEDULER:
        start_scheduler()
        await sync_scheduler_jobs()
    yield
    # Shutdown lifecycle
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    if settings.ENABLE_BACKGROUND_SCHEDULER:
        stop_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-Ready Real-Time Weather & Multi-Hazard Data Infrastructure for AEGIS Alert Platform",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Request ID & Security Headers Middleware
@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# 3. Standard Error Envelope Handlers
@app.exception_handler(AegisCoreException)
async def aegis_exception_handler(request: Request, exc: AegisCoreException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        headers={"X-Request-ID": req_id},
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "messageKey": f"errors.{exc.code.lower()}",
                "requestId": req_id,
                "details": exc.details
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.encoders import jsonable_encoder
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        errs = jsonable_encoder(exc.errors())
    except Exception:
        errs = str(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        headers={"X-Request-ID": req_id},
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload format.",
                "messageKey": "errors.validation_error",
                "requestId": req_id,
                "details": errs
            }
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        headers={"X-Request-ID": req_id},
        content={
            "success": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail if isinstance(exc.detail, str) else "Request processing error.",
                "messageKey": f"errors.http_{exc.status_code}",
                "requestId": req_id,
                "details": exc.detail if not isinstance(exc.detail, str) else None
            }
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(f"[{req_id}] Unhandled Exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={"X-Request-ID": req_id},
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while processing emergency telemetry.",
                "messageKey": "errors.internal_server_error",
                "requestId": req_id
            }
        }
    )


# 4. Top-level Container Orchestrator Health Probe
@app.get("/health", tags=["System Health & Observability"])
async def root_health(db: AsyncSession = Depends(get_db)):
    """Top-level health probe for Kubernetes/Docker container lifecycle."""
    return await check_overall_health(db)


import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# 5. Static Files Directory Mount for Incident Media
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 6. Include Master API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Also mount on /api for seamless backward compatibility with existing frontend
app.include_router(api_router, prefix="/api")

# Mount tRPC compatibility router for mobile/web client bridges
app.include_router(trpc_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "docs_url": "/docs",
        "api_v1": "/api/v1",
        "health": "/health"
    }
