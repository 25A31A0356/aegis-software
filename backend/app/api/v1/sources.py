"""
AEGIS UNIFIED DATA CORE - Data Sources & Field Mappings Management API
/api/v1/sources
Provides Administrator CRUD, secure credential encryption, Live API testing with SSRF protection,
and automatic field detection preview.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from backend.app.database.session import get_db
from backend.app.database.models import DataSource, FieldMapping, AuditLog, User
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.source import (
    DataSourceCreate, DataSourceRead,
    ApiTestRequest, ApiTestResponse, FieldMappingRead
)
from backend.app.core.encryption import SecretVault
from backend.app.core.ssrf import SSRFGuard
from backend.app.providers.registry import ProviderRegistry
from backend.app.ingestion.detector import FieldDetector
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.api.deps import require_admin_role, get_current_user

router = APIRouter(prefix="/sources", tags=["Data Sources Management"])


@router.get("", response_model=ApiResponse[List[DataSourceRead]])
async def list_data_sources(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """Lists all configured data sources with masked credentials."""
    stmt = select(DataSource).options(selectinload(DataSource.field_mappings)).order_by(desc(DataSource.created_at))
    res = await db.execute(stmt)
    sources = res.scalars().all()

    items = []
    for s in sources:
        decrypted = SecretVault.decrypt_secret(s.encrypted_api_key) if s.encrypted_api_key else ""
        masked = SecretVault.mask_secret(decrypted) if decrypted else None

        items.append(DataSourceRead(
            id=s.id,
            name=s.name,
            provider_code=s.provider_code,
            category=s.category,
            base_url=s.base_url,
            endpoint=s.endpoint,
            http_method=s.http_method,
            auth_type=s.auth_type,
            masked_api_key=masked,
            auth_header_name=s.auth_header_name,
            auth_query_param=s.auth_query_param,
            request_params=s.request_params or {},
            request_headers=s.request_headers or {},
            response_format=s.response_format,
            update_frequency_minutes=s.update_frequency_minutes,
            cache_duration_seconds=s.cache_duration_seconds,
            timeout_seconds=s.timeout_seconds,
            max_retries=s.max_retries,
            is_enabled=s.is_enabled,
            health_status=s.health_status,
            consecutive_failures=s.consecutive_failures,
            last_success_at=s.last_success_at,
            last_failure_at=s.last_failure_at,
            last_response_time_ms=s.last_response_time_ms,
            last_http_status=s.last_http_status,
            last_error_message=s.last_error_message,
            created_at=s.created_at,
            updated_at=s.updated_at,
            field_mappings=[
                FieldMappingRead(
                    id=m.id,
                    data_source_id=m.data_source_id,
                    external_field_path=m.external_field_path,
                    aegis_field_name=m.aegis_field_name,
                    source_unit=m.source_unit,
                    target_unit=m.target_unit,
                    transformation_rule=m.transformation_rule,
                    confidence=m.confidence,
                    is_active=m.is_active
                )
                for m in s.field_mappings
            ]
        ))

    return ApiResponse(success=True, data=items)


@router.post("", response_model=ApiResponse[DataSourceRead], status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_role)
):
    """Creates a new external data source with encrypted secrets and SSRF validation."""
    full_url = f"{payload.base_url.rstrip('/')}{payload.endpoint}"
    is_safe, ssrf_err = SSRFGuard.validate_url(full_url)
    if not is_safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SSRF Protection Error: {ssrf_err}")

    encrypted_key = SecretVault.encrypt_secret(payload.api_key_or_token) if payload.api_key_or_token else ""

    source = DataSource(
        name=payload.name,
        provider_code=payload.provider_code,
        category=payload.category.upper(),
        base_url=payload.base_url,
        endpoint=payload.endpoint,
        http_method=payload.http_method.upper(),
        auth_type=payload.auth_type,
        encrypted_api_key=encrypted_key,
        auth_header_name=payload.auth_header_name,
        auth_query_param=payload.auth_query_param,
        request_params=payload.request_params,
        request_headers=payload.request_headers,
        response_format=payload.response_format.upper(),
        update_frequency_minutes=payload.update_frequency_minutes,
        cache_duration_seconds=payload.cache_duration_seconds,
        timeout_seconds=payload.timeout_seconds,
        max_retries=payload.max_retries,
        is_enabled=payload.is_enabled,
        health_status="ACTIVE" if payload.is_enabled else "INACTIVE"
    )
    db.add(source)
    await db.flush()

    if payload.field_mappings:
        for m in payload.field_mappings:
            mapping = FieldMapping(
                data_source_id=source.id,
                external_field_path=m.external_field_path,
                aegis_field_name=m.aegis_field_name,
                source_unit=m.source_unit,
                target_unit=m.target_unit,
                transformation_rule=m.transformation_rule,
                confidence=m.confidence,
                is_active=m.is_active
            )
            db.add(mapping)

    # Record Audit Log
    audit = AuditLog(
        user_email=admin.email,
        action="DATA_SOURCE_CREATED",
        resource_type="DataSource",
        resource_id=source.id,
        details={"name": source.name, "category": source.category, "provider": source.provider_code}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(source)

    decrypted = SecretVault.decrypt_secret(source.encrypted_api_key) if source.encrypted_api_key else ""
    masked = SecretVault.mask_secret(decrypted) if decrypted else None

    return ApiResponse(
        success=True,
        data=DataSourceRead(
            id=source.id,
            name=source.name,
            provider_code=source.provider_code,
            category=source.category,
            base_url=source.base_url,
            endpoint=source.endpoint,
            http_method=source.http_method,
            auth_type=source.auth_type,
            masked_api_key=masked,
            auth_header_name=source.auth_header_name,
            auth_query_param=source.auth_query_param,
            request_params=source.request_params,
            request_headers=source.request_headers,
            response_format=source.response_format,
            update_frequency_minutes=source.update_frequency_minutes,
            cache_duration_seconds=source.cache_duration_seconds,
            timeout_seconds=source.timeout_seconds,
            max_retries=source.max_retries,
            is_enabled=source.is_enabled,
            health_status=source.health_status,
            consecutive_failures=source.consecutive_failures,
            last_response_time_ms=source.last_response_time_ms,
            created_at=source.created_at,
            updated_at=source.updated_at,
            field_mappings=[]
        )
    )


@router.post("/test", response_model=ApiResponse[ApiTestResponse])
async def test_api_endpoint(
    payload: ApiTestRequest,
    admin: User = Depends(require_admin_role)
):
    """
    Executes a real-time live test against an external endpoint.
    Performs SSRF validation, measures response latency, inspects format,
    and runs automatic field detection with confidence scoring.
    """
    full_url = f"{payload.base_url.rstrip('/')}{payload.endpoint}"
    is_safe, ssrf_err = SSRFGuard.validate_url(full_url)
    if not is_safe:
        return ApiResponse(
            success=False,
            data=ApiTestResponse(
                connection_status="FAILED",
                validation_status="SSRF_REJECTED",
                error_message=f"SSRF Protection Error: {ssrf_err}"
            )
        )

    headers = dict(payload.request_headers or {})
    params = dict(payload.request_params or {})

    if payload.auth_type == "BEARER_TOKEN" and payload.api_key_or_token:
        headers["Authorization"] = f"Bearer {payload.api_key_or_token}"
    elif payload.auth_type == "API_KEY_HEADER" and payload.api_key_or_token:
        header_name = payload.auth_header_name or "X-API-Key"
        headers[header_name] = payload.api_key_or_token
    elif payload.auth_type == "API_KEY_QUERY" and payload.api_key_or_token:
        param_name = payload.auth_query_param or "api_key"
        params[param_name] = payload.api_key_or_token

    provider = ProviderRegistry.get_provider(
        provider_code="custom_http",
        name="API Test Instance",
        base_url=payload.base_url,
        endpoint=payload.endpoint,
        api_key=payload.api_key_or_token,
        headers=headers,
        params=params,
        timeout_seconds=payload.timeout_seconds
    )

    fetch_result = await provider.fetch()

    if not fetch_result.success:
        return ApiResponse(
            success=True,
            data=ApiTestResponse(
                connection_status="FAILED",
                http_status=fetch_result.status_code,
                response_time_ms=fetch_result.response_time_ms,
                response_format=payload.response_format,
                error_message=fetch_result.error_message
            )
        )

    # Run Automatic Field Detection on successful payload
    detected = FieldDetector.detect_fields(fetch_result.raw_data)

    # Generate normalized preview snippet
    parsed_records = provider.parse(fetch_result.raw_data)
    preview_norm = None
    if parsed_records:
        preview_norm = parsed_records[0]

    return ApiResponse(
        success=True,
        data=ApiTestResponse(
            connection_status="SUCCESS",
            http_status=fetch_result.status_code or 200,
            response_time_ms=round(fetch_result.response_time_ms, 2),
            response_format=payload.response_format,
            raw_response_snippet=fetch_result.raw_data,
            detected_fields=detected,
            validation_status="VALID",
            normalized_preview=preview_norm
        )
    )


@router.post("/{source_id}/trigger", response_model=ApiResponse[dict])
async def trigger_source_ingestion(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_role)
):
    """Manually triggers an on-demand ingestion run for a data source."""
    result = await IngestionPipeline.run_pipeline_for_source(db, source_id)
    return ApiResponse(success=True, data=result)


@router.delete("/{source_id}", response_model=ApiResponse[dict])
async def delete_data_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_role)
):
    """Deletes a data source and its associated mappings."""
    stmt = select(DataSource).where(DataSource.id == source_id)
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found.")

    await db.delete(source)
    audit = AuditLog(
        user_email=admin.email,
        action="DATA_SOURCE_DELETED",
        resource_type="DataSource",
        resource_id=source_id,
        details={"name": source.name}
    )
    db.add(audit)
    await db.commit()

    return ApiResponse(success=True, data={"id": source_id, "deleted": True})
