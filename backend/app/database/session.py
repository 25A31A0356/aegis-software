"""
AEGIS UNIFIED DATA CORE - Database Session & Connection Management
Supports async SQLAlchemy 2.0 sessions with PostgreSQL / PostGIS and SQLite fallback for local testing.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.database.base import Base
from backend.app.database.models import User, DataSource
from backend.app.utils.logger import logger

# Build async connection URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configure engine
engine_kwargs = {}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

try:
    engine = create_async_engine(db_url, echo=settings.DEBUG, **engine_kwargs)
except Exception as e:
    # Fallback to local SQLite if PostgreSQL is not reachable locally during offline dev
    logger.warning(f"Could not connect to {db_url}: {e}. Falling back to SQLite for local workspace runtime.")
    db_url = "sqlite+aiosqlite:///./aegis_local.db"
    engine = create_async_engine(db_url, echo=settings.DEBUG, connect_args={"check_same_thread": False})

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for database session management."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initializes database tables and bootstraps initial admin user."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Check if default admin exists
        result = await session.execute(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
        admin = result.scalars().first()
        if not admin:
            admin_user = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                full_name="AEGIS System Administrator",
                role="admin",
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Bootstrapped default administrator: {settings.DEFAULT_ADMIN_EMAIL}")
