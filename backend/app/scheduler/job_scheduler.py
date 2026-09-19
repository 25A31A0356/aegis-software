"""
AEGIS UNIFIED DATA CORE - Background Job Scheduler
Coordinates scheduled asynchronous data ingestion across all enabled provider sources.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from backend.app.database.session import async_session_factory
from backend.app.database.models import DataSource
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.utils.logger import logger

scheduler = AsyncIOScheduler()


async def ingest_source_job(source_id: str):
    """Worker task executing scheduled ingestion pipeline for a single source."""
    async with async_session_factory() as session:
        try:
            logger.info(f"Triggering scheduled ingestion for source ID: {source_id}")
            result = await IngestionPipeline.run_pipeline_for_source(session, source_id)
            logger.info(f"Ingestion result for source {source_id}: {result.get('status')}")
        except Exception as e:
            logger.error(f"Scheduled ingestion failed for source {source_id}: {e}")


async def sync_scheduler_jobs():
    """Syncs active DataSources from database with the APScheduler job table."""
    async with async_session_factory() as session:
        result = await session.execute(select(DataSource).where(DataSource.is_enabled == True))
        active_sources = result.scalars().all()

        existing_job_ids = {job.id for job in scheduler.get_jobs()}
        current_source_ids = {f"source_{s.id}" for s in active_sources}

        # Remove stale jobs
        for job_id in existing_job_ids:
            if job_id.startswith("source_") and job_id not in current_source_ids:
                scheduler.remove_job(job_id)
                logger.info(f"Removed scheduler job: {job_id}")

        # Add or update active jobs
        for source in active_sources:
            job_id = f"source_{source.id}"
            interval_mins = max(1, source.update_frequency_minutes)
            
            if job_id not in existing_job_ids:
                scheduler.add_job(
                    ingest_source_job,
                    trigger=IntervalTrigger(minutes=interval_mins),
                    id=job_id,
                    args=[source.id],
                    replace_existing=True
                )
                logger.info(f"Registered background ingestion for '{source.name}' every {interval_mins} mins.")


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("AEGIS Background Ingestion Scheduler started.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("AEGIS Background Ingestion Scheduler stopped.")
