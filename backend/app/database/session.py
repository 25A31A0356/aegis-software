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
from backend.app.database.models import User
from backend.app.utils.logger import logger

# Build async connection URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

def create_engine_and_factory(url: str):
    engine_kwargs = {}
    if "sqlite" in url:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    eng = create_async_engine(url, echo=settings.DEBUG, **engine_kwargs)
    factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return eng, factory

engine, async_session_factory = create_engine_and_factory(db_url)


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
    global engine, async_session_factory
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        if settings.ENVIRONMENT == "production":
            logger.error(
                f"FATAL: Database connection to PostgreSQL '{db_url}' failed ({e}). "
                "Production environment strictly requires PostgreSQL/PostGIS. Aborting startup."
            )
            raise e
        logger.warning(
            f"Database connection to '{db_url}' failed ({e}). "
            "Falling back to local SQLite ('sqlite+aiosqlite:///./aegis_local.db') for offline development."
        )
        engine, _ = create_engine_and_factory("sqlite+aiosqlite:///./aegis_local.db")
        async_session_factory.configure(bind=engine)
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

    try:
        from backend.app.database.seeds import seed_database
        await seed_database()
    except Exception as e:
        logger.warning(f"Seed database skipped or error: {e}")
