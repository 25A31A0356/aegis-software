"""
AEGIS UNIFIED DATA CORE - Core Configuration
Enhanced with Phase 1 Foundation Validation & Security Guardrails
"""
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "AEGIS UNIFIED DATA CORE"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    ENABLE_DEV_MOCKS: bool = False

    # Server binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://localhost:80",
        "http://localhost",
    ]
    CORS_ORIGINS: Optional[str] = None

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if i]
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip() for i in v if i]
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://localhost:80",
            "http://localhost",
        ]

    # Database & Storage
    DATABASE_URL: str = "postgresql+asyncpg://aegis_user:aegis_secure_password_2026@postgres:5432/aegis_db"
    DATABASE_SYNC_URL: Optional[str] = "postgresql://aegis_user:aegis_secure_password_2026@postgres:5432/aegis_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis Cache & Broker
    REDIS_URL: str = "redis://redis:6379/0"
    CACHE_DEFAULT_TTL_SEC: int = 300  # 5 minutes

    # Security & Encryption
    AEGIS_SECRET_KEY: str = "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="
    JWT_SECRET: str = "aegis_jwt_super_secret_signing_key_production_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Admin Default Credentials
    DEFAULT_ADMIN_EMAIL: str = "admin@aegis.gov.in"
    DEFAULT_ADMIN_PASSWORD: str = "AegisAdmin@2026!"

    # Application Client Keys
    AEGIS_WEB_CLIENT_KEY: Optional[str] = "aegis_web_client_secure_key_2026"
    AEGIS_APP_CLIENT_KEY: Optional[str] = "aegis_app_client_secure_key_2026"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 120

    # SSRF & Outbound HTTP Security
    SSRF_PROTECTION_ENABLED: bool = True
    HTTP_TIMEOUT_SECONDS: float = 15.0
    HTTP_MAX_RETRIES: int = 3

    # External Provider Credentials
    NASA_FIRMS_MAP_KEY: Optional[str] = ""
    IMD_API_KEY: Optional[str] = ""
    CWC_API_KEY: Optional[str] = ""
    CPCB_API_KEY: Optional[str] = ""
    OPEN_METEO_API_KEY: Optional[str] = ""
    MAPS_ROUTING_KEY: Optional[str] = ""
    GEMINI_API_KEY: Optional[str] = ""
    EXPO_ACCESS_TOKEN: Optional[str] = ""
    FCM_SERVER_KEY: Optional[str] = ""

    # Scheduler & Ingestion
    ENABLE_BACKGROUND_SCHEDULER: bool = True
    DEFAULT_INGESTION_INTERVAL_MINUTES: int = 5

    # SOS Responder Network Configuration
    SOS_INITIAL_RADIUS_KM: float = 10.0
    SOS_MAX_RADIUS_KM: float = 20.0
    SOS_EXPIRATION_MINUTES: int = 60
    SOS_OFFER_TIMEOUT_SECONDS: int = 45
    SOS_ROUTE_RECALC_METERS: float = 150.0
    SOS_MAX_CANDIDATES: int = 10

    @model_validator(mode="after")
    def validate_production_guardrails(self) -> "Settings":
        """Fail-fast validation for production deployments."""
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET in [
                "secret",
                "default",
                "aegis_jwt_super_secret_signing_key_production_2026",
                "changethisinproduction"
            ]:
                raise ValueError("FATAL: Default JWT_SECRET is forbidden in production environment.")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("FATAL: Wildcard CORS origin ('*') is forbidden in production environment.")
            if self.ENABLE_DEV_MOCKS:
                raise ValueError("FATAL: ENABLE_DEV_MOCKS must be False in production environment.")
        return self


settings = Settings()
