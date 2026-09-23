"""0002_phase2_to_phase10_complete

Revision ID: 0002_phase2_to_phase10_complete
Revises: 0001_initial_schema
Create Date: 2026-09-21 23:59:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_phase2_to_phase10_complete'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update aegis_alerts with official authorization columns if missing
    # In SQLite or Postgres, we can add them safely
    try:
        op.add_column('aegis_alerts', sa.Column('is_authorized_official', sa.Boolean(), nullable=False, server_default=sa.true()))
        op.add_column('aegis_alerts', sa.Column('authorized_by_user_id', sa.String(length=36), nullable=True))
        op.add_column('aegis_alerts', sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('aegis_alerts', sa.Column('authorization_notes', sa.Text(), nullable=True))
    except Exception:
        pass

    # 2. aegis_sos_signals
    op.create_table(
        'aegis_sos_signals',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('device_id', sa.String(length=100), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('requester_user_id', sa.String(length=36), nullable=True),
        sa.Column('caller_name', sa.String(length=100), nullable=False, server_default='Citizen in Distress'),
        sa.Column('caller_phone', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('emergency_type', sa.String(length=50), nullable=False, server_default='general'),
        sa.Column('severity', sa.String(length=30), nullable=False, server_default='CRITICAL'),
        sa.Column('short_message', sa.String(length=500), nullable=True, server_default=''),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('accuracy_meters', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('location_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_location_update', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=False, server_default='India'),
        sa.Column('battery_percent', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('medical_notes', sa.Text(), nullable=True),
        sa.Column('casualties_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True, unique=True),
        sa.Column('sync_status', sa.String(length=30), nullable=False, server_default='SYNCED'),
        sa.Column('raw_payload', sa.JSON(), nullable=False),
        sa.Column('accepted_by', sa.String(length=36), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_aegis_sos_signals_status', 'aegis_sos_signals', ['status'])
    op.create_index('ix_aegis_sos_signals_lat_lng', 'aegis_sos_signals', ['latitude', 'longitude'])

    # 3. aegis_sos_responder_candidates
    op.create_table(
        'aegis_sos_responder_candidates',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('sos_id', sa.String(length=36), sa.ForeignKey('aegis_sos_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('responder_user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='OFFERED'),
        sa.Column('distance_km', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('offered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_sos_candidate_unique', 'aegis_sos_responder_candidates', ['sos_id', 'responder_user_id'], unique=True)

    # 4. aegis_sos_assignments
    op.create_table(
        'aegis_sos_assignments',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('sos_id', sa.String(length=36), sa.ForeignKey('aegis_sos_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('responder_user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='ACTIVE'),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('arrived_on_site_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_reason', sa.String(length=255), nullable=True),
        sa.Column('route_geometry', sa.JSON(), nullable=False),
        sa.Column('distance_meters', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('eta_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_responder_lat', sa.Float(), nullable=True),
        sa.Column('last_responder_lon', sa.Float(), nullable=True),
        sa.Column('last_responder_update', sa.DateTime(timezone=True), nullable=True),
        sa.Column('speed_kmh', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('heading_degrees', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('is_stale_gps', sa.Boolean(), nullable=False, server_default=sa.false())
    )

    # 5. aegis_sos_location_updates
    op.create_table(
        'aegis_sos_location_updates',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('sos_id', sa.String(length=36), sa.ForeignKey('aegis_sos_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False, server_default='REQUESTER'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('accuracy_meters', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('battery_percent', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('speed_kmh', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 6. aegis_sos_status_history
    op.create_table(
        'aegis_sos_status_history',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('sos_id', sa.String(length=36), sa.ForeignKey('aegis_sos_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('old_status', sa.String(length=50), nullable=False),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('changed_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 7. aegis_sos_notifications
    op.create_table(
        'aegis_sos_notifications',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('sos_id', sa.String(length=36), sa.ForeignKey('aegis_sos_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_type', sa.String(length=30), nullable=False),
        sa.Column('recipient_id', sa.String(length=100), nullable=False),
        sa.Column('channel', sa.String(length=30), nullable=False, server_default='WEBSOCKET'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='SENT'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 8. aegis_safe_events
    op.create_table(
        'aegis_safe_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('device_id', sa.String(length=100), nullable=True),
        sa.Column('sos_id', sa.String(length=36), sa.ForeignKey('aegis_sos_signals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_name', sa.String(length=100), nullable=False, server_default='Citizen'),
        sa.Column('user_phone', sa.String(length=50), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SAFE'),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('accuracy_meters', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=False, server_default='India'),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True, unique=True),
        sa.Column('sync_status', sa.String(length=30), nullable=False, server_default='SYNCED'),
        sa.Column('contacts_notified_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 9. aegis_emergency_contacts
    op.create_table(
        'aegis_emergency_contacts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('aegis_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('relationship', sa.String(length=50), nullable=False, server_default='Family'),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('is_trusted', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_on_sos', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_on_safe', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 10. aegis_emergency_services
    op.create_table(
        'aegis_emergency_services',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('service_code', sa.String(length=50), nullable=False, unique=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('phone_numbers', sa.JSON(), nullable=False),
        sa.Column('alternate_phone', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True, server_default='All India'),
        sa.Column('district', sa.String(length=100), nullable=True, server_default='All Districts'),
        sa.Column('action_types', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_automated_dispatch_integrated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('dispatch_endpoint', sa.String(length=1024), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('display_priority', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 11. aegis_incident_reports
    op.create_table(
        'aegis_incident_reports',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('anonymous_reporter_id', sa.String(length=100), nullable=True),
        sa.Column('reporter_name', sa.String(length=100), nullable=True, server_default='Citizen Observer'),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='OTHER'),
        sa.Column('hazard_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False, server_default='MODERATE'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SUBMITTED'),
        sa.Column('verification_status', sa.String(length=50), nullable=False, server_default='UNVERIFIED'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('verification_source', sa.String(length=100), nullable=False, server_default='CITIZEN_SUBMISSION'),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='COMMUNITY'),
        sa.Column('source_type', sa.String(length=50), nullable=False, server_default='COMMUNITY_REPORT'),
        sa.Column('verified_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=255), nullable=True),
        sa.Column('operator_notes', sa.Text(), nullable=True),
        sa.Column('linked_sos_id', sa.String(length=36), nullable=True),
        sa.Column('linked_incident_id', sa.String(length=36), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('accuracy_meters', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=False, server_default='India'),
        sa.Column('media_urls', sa.JSON(), nullable=False),
        sa.Column('media_type', sa.String(length=30), nullable=True, server_default='NONE'),
        sa.Column('upvotes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('downvotes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_aegis_reports_category', 'aegis_incident_reports', ['category'])
    op.create_index('ix_aegis_reports_status', 'aegis_incident_reports', ['status'])

    # 12. aegis_report_votes
    op.create_table(
        'aegis_report_votes',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('report_id', sa.String(length=36), sa.ForeignKey('aegis_incident_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('voter_id', sa.String(length=100), nullable=False),
        sa.Column('vote_type', sa.String(length=20), nullable=False, server_default='UPVOTE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_report_voter_unique', 'aegis_report_votes', ['report_id', 'voter_id'], unique=True)

    # 13. aegis_activity_events
    op.create_table(
        'aegis_activity_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=30), nullable=False, server_default='MODERATE'),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='COMMUNITY'),
        sa.Column('verification_status', sa.String(length=50), nullable=False, server_default='UNVERIFIED_COMMUNITY'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 14. aegis_safe_zones
    op.create_table(
        'aegis_safe_zones',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('zone_type', sa.String(length=50), nullable=False, server_default='RELIEF_SHELTER'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('current_occupancy', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('amenities', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 15. aegis_user_preferences
    op.create_table(
        'aegis_user_preferences',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('aegis_users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('saved_locations', sa.JSON(), nullable=False),
        sa.Column('hazard_subscriptions', sa.JSON(), nullable=False),
        sa.Column('push_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sms_alerts_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('is_responder_opted_in', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_known_lat', sa.Float(), nullable=True),
        sa.Column('last_known_lng', sa.Float(), nullable=True),
        sa.Column('last_location_time', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('capabilities', sa.JSON(), nullable=False),
        sa.Column('vehicle_type', sa.String(length=50), nullable=True, server_default='MOTORCYCLE'),
        sa.Column('max_active_assignments', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('heading_degrees', sa.Float(), nullable=True),
        sa.Column('speed_kmh', sa.Float(), nullable=True),
        sa.Column('gps_accuracy_m', sa.Float(), nullable=True),
        sa.Column('emergency_contacts', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 16. aegis_district_registry
    op.create_table(
        'aegis_district_registry',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('district_name', sa.String(length=100), nullable=False),
        sa.Column('state_name', sa.String(length=100), nullable=False),
        sa.Column('country', sa.String(length=50), nullable=False, server_default='India'),
        sa.Column('is_ut', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('elevation_m', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('aliases', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_district_state_name', 'aegis_district_registry', ['state_name', 'district_name'])
    op.create_index('idx_district_spatial_lat_lng', 'aegis_district_registry', ['latitude', 'longitude'])

    # 17. aegis_device_tokens
    op.create_table(
        'aegis_device_tokens',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('device_id', sa.String(length=100), nullable=False),
        sa.Column('push_token', sa.String(length=512), nullable=False, unique=True),
        sa.Column('platform', sa.String(length=20), nullable=False, server_default='ANDROID'),
        sa.Column('provider', sa.String(length=20), nullable=False, server_default='EXPO'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_registered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_device_token_user_platform', 'aegis_device_tokens', ['user_id', 'platform'])

    # 18. aegis_notification_deliveries
    op.create_table(
        'aegis_notification_deliveries',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('recipient_type', sa.String(length=30), nullable=False, server_default='USER'),
        sa.Column('recipient_id', sa.String(length=100), nullable=False),
        sa.Column('device_token', sa.String(length=512), nullable=True),
        sa.Column('channel', sa.String(length=30), nullable=False, server_default='PUSH'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('provider_response', sa.JSON(), nullable=False),
        sa.Column('error_reason', sa.Text(), nullable=True),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_notif_deliveries_status', 'aegis_notification_deliveries', ['status'])
    op.create_index('ix_notif_deliveries_recipient', 'aegis_notification_deliveries', ['recipient_id'])


def downgrade() -> None:
    op.drop_table('aegis_notification_deliveries')
    op.drop_table('aegis_device_tokens')
    op.drop_table('aegis_district_registry')
    op.drop_table('aegis_user_preferences')
    op.drop_table('aegis_safe_zones')
    op.drop_table('aegis_activity_events')
    op.drop_table('aegis_report_votes')
    op.drop_table('aegis_incident_reports')
    op.drop_table('aegis_emergency_services')
    op.drop_table('aegis_emergency_contacts')
    op.drop_table('aegis_safe_events')
    op.drop_table('aegis_sos_notifications')
    op.drop_table('aegis_sos_status_history')
    op.drop_table('aegis_sos_location_updates')
    op.drop_table('aegis_sos_assignments')
    op.drop_table('aegis_sos_responder_candidates')
    op.drop_table('aegis_sos_signals')
