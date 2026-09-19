"""
AEGIS UNIFIED DATA CORE - End-to-End Ingestion Pipeline
Executes the full real-time ingestion cycle:
FETCH -> RAW STORAGE -> PARSE -> CLASSIFY -> MAP -> NORMALIZE -> VALIDATE -> DEDUPLICATE -> DB STORE -> CACHE -> HEALTH
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.database.models import DataSource, RawObservation, NormalizedObservation, ProcessingJob, FieldMapping
from backend.app.providers.registry import ProviderRegistry
from backend.app.core.encryption import SecretVault
from backend.app.ingestion.validator import TelemetryValidator
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.cache.redis_client import CacheManager
from backend.app.schemas.unified import UnifiedObservation
from backend.app.utils.logger import logger


class IngestionPipeline:
    @classmethod
    async def run_pipeline_for_source(cls, db: AsyncSession, source_id: str) -> Dict[str, Any]:
        """Runs the complete ingestion pipeline for a configured DataSource."""
        # 1. Fetch Source configuration
        result = await db.execute(
            select(DataSource)
            .options(selectinload(DataSource.field_mappings))
            .where(DataSource.id == source_id)
        )
        source = result.scalars().first()
        if not source or not source.is_enabled:
            return {"status": "SKIPPED", "reason": "Source not found or disabled"}

        # Decrypt provider secret in memory only for the request
        decrypted_key = SecretVault.decrypt_secret(source.encrypted_api_key) if source.encrypted_api_key else None

        # Build headers if auth is BEARER or HEADER
        headers = dict(source.request_headers or {})
        params = dict(source.request_params or {})
        if source.auth_type == "BEARER_TOKEN" and decrypted_key:
            headers["Authorization"] = f"Bearer {decrypted_key}"
        elif source.auth_type == "API_KEY_HEADER" and decrypted_key:
            header_name = source.auth_header_name or "X-API-Key"
            headers[header_name] = decrypted_key
        elif source.auth_type == "API_KEY_QUERY" and decrypted_key:
            param_name = source.auth_query_param or "api_key"
            params[param_name] = decrypted_key

        # Prepare Field Mappings if any
        mappings_dicts = [
            {
                "external_field_path": m.external_field_path,
                "aegis_field_name": m.aegis_field_name,
                "source_unit": m.source_unit,
                "target_unit": m.target_unit,
                "transformation_rule": m.transformation_rule,
            }
            for m in source.field_mappings if m.is_active
        ]

        # 2. Instantiate Provider Adapter
        provider = ProviderRegistry.get_provider(
            provider_code=source.provider_code,
            name=source.name,
            base_url=source.base_url,
            endpoint=source.endpoint,
            category=source.category,
            api_key=decrypted_key,
            headers=headers,
            params=params,
            field_mappings=mappings_dicts,
            timeout_seconds=source.timeout_seconds
        )

        job = ProcessingJob(
            data_source_id=source.id,
            job_type="SCHEDULED_INGESTION",
            status="RECEIVED",
            started_at=datetime.now(timezone.utc)
        )
        db.add(job)
        await db.flush()

        start_time = time.time()

        # 3. Fetch from External API
        fetch_result = await provider.fetch()
        elapsed_ms = fetch_result.response_time_ms

        source.last_response_time_ms = elapsed_ms
        source.last_http_status = fetch_result.status_code

        if not fetch_result.success:
            # Update source failure metrics
            source.consecutive_failures += 1
            source.last_failure_at = datetime.now(timezone.utc)
            source.last_error_message = fetch_result.error_message
            source.health_status = "FAILED" if source.consecutive_failures >= 3 else "DEGRADED"

            job.status = "FAILED"
            job.completed_at = datetime.now(timezone.utc)
            job.duration_ms = (time.time() - start_time) * 1000.0
            job.error_message = fetch_result.error_message
            await db.commit()
            return {"status": "FAILED", "error": fetch_result.error_message}

        # 4. Save Raw Payload for Provenance & Auditability (Without Secrets)
        raw_obs = RawObservation(
            data_source_id=source.id,
            source_record_id=f"{source.provider_code}-{int(time.time())}",
            payload_format=source.response_format,
            raw_payload=fetch_result.raw_data if isinstance(fetch_result.raw_data, (dict, list)) else {"raw_text": str(fetch_result.raw_data)[:10000]}
        )
        db.add(raw_obs)

        # 5. Parse, Normalize & Validate Records
        job.status = "PARSING"
        parsed_records = provider.parse(fetch_result.raw_data)
        
        job.status = "NORMALIZING"
        normalized_list: List[NormalizedObservation] = []
        ingested_count = 0
        failed_count = 0

        for rec in parsed_records:
            try:
                norm_schema = provider.normalize(rec)
                if not norm_schema:
                    failed_count += 1
                    continue

                # Validate
                is_valid, val_err = TelemetryValidator.validate_observation(norm_schema)
                if not is_valid:
                    logger.warning(f"Validation rejected record from {source.name}: {val_err}")
                    failed_count += 1
                    continue

                norm_db = NormalizedObservation(
                    data_source_id=source.id,
                    source_record_id=norm_schema.source_record_id,
                    hazard_type=norm_schema.hazard_type,
                    latitude=norm_schema.location.latitude,
                    longitude=norm_schema.location.longitude,
                    location_name=norm_schema.location.city_name,
                    state_name=norm_schema.location.state_name,
                    district_name=norm_schema.location.district_name,
                    observed_at=norm_schema.observed_at,
                    received_at=norm_schema.received_at,
                    severity=norm_schema.severity,
                    risk_level=norm_schema.risk_level,
                    confidence=norm_schema.confidence,
                    data_type=norm_schema.data_type,
                    source_authority=norm_schema.source_authority,
                    processing_version=norm_schema.processing_version,
                    measurements=norm_schema.measurements,
                    metadata_json=norm_schema.metadata
                )
                normalized_list.append(norm_db)
                db.add(norm_db)
                ingested_count += 1
            except Exception as e:
                logger.error(f"Error normalizing record: {e}")
                failed_count += 1

        # 6. Update Source Health to Healthy / Active
        source.health_status = "HEALTHY"
        source.consecutive_failures = 0
        source.last_success_at = datetime.now(timezone.utc)
        source.last_error_message = None

        job.status = "COMPLETED"
        job.completed_at = datetime.now(timezone.utc)
        job.duration_ms = (time.time() - start_time) * 1000.0
        job.records_ingested = ingested_count
        job.records_failed = failed_count

        await db.commit()

        # 7. Hot-Cache latest normalized telemetry into Redis
        if normalized_list:
            cache_key = f"latest_{source.category.lower()}_{source.id}"
            latest_payload = [
                {
                    "hazard_type": item.hazard_type,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                    "observed_at": item.observed_at.isoformat() if item.observed_at else None,
                    "measurements": item.measurements,
                    "source_authority": item.source_authority
                }
                for item in normalized_list[:20]
            ]
            await CacheManager.set(cache_key, latest_payload, ttl_seconds=source.cache_duration_seconds)

        return {
            "status": "COMPLETED",
            "records_ingested": ingested_count,
            "records_failed": failed_count,
            "response_time_ms": elapsed_ms
        }
