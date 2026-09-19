"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-19 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. aegis_users
    op.create_table(
        'aegis_users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='public'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_aegis_users_email', 'aegis_users', ['email'], unique=True)

    # 2. aegis_data_sources
    op.create_table(
        'aegis_data_sources',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('provider_code', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('base_url', sa.String(length=1024), nullable=False),
        sa.Column('endpoint', sa.String(length=1024), nullable=False, server_default=''),
        sa.Column('http_method', sa.String(length=10), nullable=False, server_default='GET'),
        sa.Column('auth_type', sa.String(length=50), nullable=False, server_default='NONE'),
        sa.Column('encrypted_api_key', sa.Text(), nullable=True),
        sa.Column('auth_header_name', sa.String(length=100), nullable=True),
        sa.Column('auth_query_param', sa.String(length=100), nullable=True),
        sa.Column('request_params', sa.JSON(), nullable=False),
        sa.Column('request_headers', sa.JSON(), nullable=False),
        sa.Column('response_format', sa.String(length=20), nullable=False, server_default='JSON'),
        sa.Column('update_frequency_minutes', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('cache_duration_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('timeout_seconds', sa.Float(), nullable=False, server_default='15.0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('health_status', sa.String(length=50), nullable=False, server_default='INACTIVE'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_response_time_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('last_http_status', sa.Integer(), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_aegis_data_sources_provider_code', 'aegis_data_sources', ['provider_code'])
    op.create_index('ix_aegis_data_sources_category', 'aegis_data_sources', ['category'])

    # 3. aegis_field_mappings
    op.create_table(
        'aegis_field_mappings',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('data_source_id', sa.String(length=36), sa.ForeignKey('aegis_data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_field_path', sa.String(length=255), nullable=False),
        sa.Column('aegis_field_name', sa.String(length=100), nullable=False),
        sa.Column('source_unit', sa.String(length=50), nullable=True, server_default='standard'),
        sa.Column('target_unit', sa.String(length=50), nullable=True, server_default='standard'),
        sa.Column('transformation_rule', sa.String(length=100), nullable=False, server_default='direct'),
        sa.Column('confidence', sa.String(length=20), nullable=False, server_default='HIGH'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true())
    )

    # 4. aegis_raw_observations
    op.create_table(
        'aegis_raw_observations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('data_source_id', sa.String(length=36), sa.ForeignKey('aegis_data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_record_id', sa.String(length=255), nullable=True),
        sa.Column('payload_format', sa.String(length=20), nullable=False, server_default='JSON'),
        sa.Column('raw_payload', sa.JSON(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 5. aegis_normalized_observations
    op.create_table(
        'aegis_normalized_observations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('data_source_id', sa.String(length=36), sa.ForeignKey('aegis_data_sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_record_id', sa.String(length=255), nullable=True),
        sa.Column('hazard_type', sa.String(length=50), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('state_name', sa.String(length=100), nullable=True),
        sa.Column('district_name', sa.String(length=100), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='moderate'),
        sa.Column('risk_level', sa.String(length=50), nullable=False, server_default='MODERATE'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('data_type', sa.String(length=50), nullable=False, server_default='official_observation'),
        sa.Column('source_authority', sa.String(length=100), nullable=False),
        sa.Column('processing_version', sa.String(length=20), nullable=False, server_default='1.0.0'),
        sa.Column('measurements', sa.JSON(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_obs_hazard_time', 'aegis_normalized_observations', ['hazard_type', 'observed_at'])
    op.create_index('ix_obs_geo_time', 'aegis_normalized_observations', ['latitude', 'longitude', 'observed_at'])

    # 6. aegis_alerts
    op.create_table(
        'aegis_alerts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('alert_code', sa.String(length=100), nullable=False, unique=True),
        sa.Column('hazard_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('headline', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=True),
        sa.Column('state_name', sa.String(length=100), nullable=True),
        sa.Column('district_name', sa.String(length=100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('radius_km', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('geometry_geojson', sa.JSON(), nullable=True),
        sa.Column('source_agency', sa.String(length=255), nullable=False),
        sa.Column('bulletin_id', sa.String(length=100), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provenance_type', sa.String(length=50), nullable=False, server_default='official_warning'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 7. aegis_audit_logs
    op.create_table(
        'aegis_audit_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('client_ip', sa.String(length=100), nullable=False, server_default='127.0.0.1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 8. aegis_processing_jobs
    op.create_table(
        'aegis_processing_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('data_source_id', sa.String(length=36), sa.ForeignKey('aegis_data_sources.id', ondelete='CASCADE'), nullable=True),
        sa.Column('job_type', sa.String(length=50), nullable=False, server_default='SCHEDULED_INGESTION'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='RECEIVED'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('records_ingested', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_table('aegis_processing_jobs')
    op.drop_table('aegis_audit_logs')
    op.drop_table('aegis_alerts')
    op.drop_table('aegis_normalized_observations')
    op.drop_table('aegis_raw_observations')
    op.drop_table('aegis_field_mappings')
    op.drop_table('aegis_data_sources')
    op.drop_table('aegis_users')
