"""0003_master_core_entities

Revision ID: 0003_master_core_entities
Revises: 0002_phase2_to_phase10_complete
Create Date: 2026-09-22 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_master_core_entities'
down_revision: Union[str, None] = '0002_phase2_to_phase10_complete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add selection_rationale to aegis_sos_responder_candidates if not exists
    try:
        op.add_column('aegis_sos_responder_candidates', sa.Column('selection_rationale', sa.Text(), nullable=True, server_default=''))
    except Exception:
        pass

    # 2. aegis_devices
    op.create_table(
        'aegis_devices',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('device_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('aegis_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=False, server_default='ANDROID'),
        sa.Column('os_version', sa.String(length=50), nullable=True),
        sa.Column('app_version', sa.String(length=50), nullable=True),
        sa.Column('device_model', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_aegis_devices_device_id', 'aegis_devices', ['device_id'], unique=True)
    op.create_index('ix_aegis_devices_user_id', 'aegis_devices', ['user_id'])
    op.create_index('ix_aegis_devices_is_active', 'aegis_devices', ['is_active'])

    # 3. aegis_report_evidence
    op.create_table(
        'aegis_report_evidence',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('report_id', sa.String(length=36), sa.ForeignKey('aegis_incident_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('uploader_id', sa.String(length=36), nullable=True),
        sa.Column('media_type', sa.String(length=30), nullable=False, server_default='PHOTO'),
        sa.Column('file_url', sa.String(length=1024), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mime_type', sa.String(length=100), nullable=False, server_default='image/jpeg'),
        sa.Column('sha256_hash', sa.String(length=64), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_aegis_report_evidence_report_id', 'aegis_report_evidence', ['report_id'])
    op.create_index('ix_aegis_report_evidence_uploader_id', 'aegis_report_evidence', ['uploader_id'])
    op.create_index('ix_aegis_report_evidence_sha256_hash', 'aegis_report_evidence', ['sha256_hash'])

    # 4. aegis_report_verifications
    op.create_table(
        'aegis_report_verifications',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('report_id', sa.String(length=36), sa.ForeignKey('aegis_incident_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operator_id', sa.String(length=36), sa.ForeignKey('aegis_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('verification_status', sa.String(length=50), nullable=False),
        sa.Column('verified_severity', sa.String(length=30), nullable=True),
        sa.Column('operator_notes', sa.Text(), nullable=True, server_default=''),
        sa.Column('rejection_reason', sa.String(length=255), nullable=True, server_default=''),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_aegis_report_verifications_report_id', 'aegis_report_verifications', ['report_id'])
    op.create_index('ix_aegis_report_verifications_operator_id', 'aegis_report_verifications', ['operator_id'])
    op.create_index('ix_aegis_report_verifications_status', 'aegis_report_verifications', ['verification_status'])

    # 5. aegis_emergency_facilities
    op.create_table(
        'aegis_emergency_facilities',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('facility_type', sa.String(length=50), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=True, server_default=''),
        sa.Column('city', sa.String(length=100), nullable=True, server_default=''),
        sa.Column('district', sa.String(length=100), nullable=True, server_default=''),
        sa.Column('state', sa.String(length=100), nullable=True, server_default=''),
        sa.Column('contact_phone', sa.String(length=50), nullable=True, server_default=''),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('current_occupancy', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('operational_status', sa.String(length=50), nullable=False, server_default='OPERATIONAL'),
        sa.Column('amenities', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_facility_geo', 'aegis_emergency_facilities', ['latitude', 'longitude'])
    op.create_index('idx_facility_type_status', 'aegis_emergency_facilities', ['facility_type', 'operational_status'])
    op.create_index('ix_aegis_emergency_facilities_district', 'aegis_emergency_facilities', ['district'])
    op.create_index('ix_aegis_emergency_facilities_state', 'aegis_emergency_facilities', ['state'])

    # 6. aegis_ai_decision_audits
    op.create_table(
        'aegis_ai_decision_audits',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('model_provider', sa.String(length=100), nullable=False, server_default='gemini-1.5-flash'),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('input_hash', sa.String(length=64), nullable=False),
        sa.Column('input_context', sa.JSON(), nullable=False),
        sa.Column('output_payload', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('authorization_status', sa.String(length=50), nullable=False, server_default='NOT_REQUIRED'),
        sa.Column('authorized_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('authorization_notes', sa.Text(), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_aegis_ai_decision_audits_request_id', 'aegis_ai_decision_audits', ['request_id'])
    op.create_index('ix_aegis_ai_decision_audits_task_type', 'aegis_ai_decision_audits', ['task_type'])
    op.create_index('ix_aegis_ai_decision_audits_input_hash', 'aegis_ai_decision_audits', ['input_hash'])
    op.create_index('ix_aegis_ai_decision_audits_auth_status', 'aegis_ai_decision_audits', ['authorization_status'])


def downgrade() -> None:
    op.drop_table('aegis_ai_decision_audits')
    op.drop_table('aegis_emergency_facilities')
    op.drop_table('aegis_report_verifications')
    op.drop_table('aegis_report_evidence')
    op.drop_table('aegis_devices')
