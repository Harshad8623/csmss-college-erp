"""add_production_indexes_notices_leaves_assignments

Revision ID: f952a5b01d0f
Revises: 1d0939bd81bd
Create Date: 2026-05-03

Performance indexes for 10,000+ students / 400+ teachers.
Targets the 6 tables that had ZERO indexes and are queried on every page load.
"""
from alembic import op

revision = 'f952a5b01d0f'
down_revision = '1d0939bd81bd'
branch_labels = None
depends_on = None


def upgrade():
    # ── notices ──────────────────────────────────────────────────────────────
    # Queried on every student/teacher dashboard load
    op.create_index('ix_notices_status_deleted',
                    'notices', ['status', 'is_deleted'], unique=False)
    op.create_index('ix_notices_posted_by',
                    'notices', ['posted_by'], unique=False)
    op.create_index('ix_notices_target_role',
                    'notices', ['target_role'], unique=False)
    op.create_index('ix_notices_target_class_id',
                    'notices', ['target_class_id'], unique=False)
    op.create_index('ix_notices_created_at',
                    'notices', ['created_at'], unique=False)

    # ── leave_applications ────────────────────────────────────────────────────
    # Queried by student (filter by student_id) and by TG/CT (join with students)
    op.create_index('ix_leaves_student_id',
                    'leave_applications', ['student_id'], unique=False)
    op.create_index('ix_leaves_tg_status',
                    'leave_applications', ['tg_status'], unique=False)
    op.create_index('ix_leaves_ct_status',
                    'leave_applications', ['ct_status'], unique=False)
    op.create_index('ix_leaves_created_at',
                    'leave_applications', ['created_at'], unique=False)
    op.create_index('ix_leaves_start_date',
                    'leave_applications', ['start_date'], unique=False)

    # ── assignments ───────────────────────────────────────────────────────────
    # Queried by subject_id (class lookup) and deadline (upcoming filter)
    op.create_index('ix_assignments_subject_id',
                    'assignments', ['subject_id'], unique=False)
    op.create_index('ix_assignments_deadline',
                    'assignments', ['deadline'], unique=False)
    op.create_index('ix_assignments_created_by',
                    'assignments', ['created_by'], unique=False)

    # ── grievances ────────────────────────────────────────────────────────────
    op.create_index('ix_grievances_student_id',
                    'grievances', ['student_id'], unique=False)
    op.create_index('ix_grievances_status',
                    'grievances', ['status'], unique=False)
    op.create_index('ix_grievances_assigned_to',
                    'grievances', ['assigned_to'], unique=False)
    op.create_index('ix_grievances_created_at',
                    'grievances', ['created_at'], unique=False)

    # ── certificates ──────────────────────────────────────────────────────────
    op.create_index('ix_certificates_student_id',
                    'certificates', ['student_id'], unique=False)
    op.create_index('ix_certificates_status',
                    'certificates', ['status'], unique=False)
    op.create_index('ix_certificates_type',
                    'certificates', ['type'], unique=False)

    # ── timetable ─────────────────────────────────────────────────────────────
    # Queried by (class_id, day) on timetable page load — critical index
    op.create_index('ix_timetable_class_day',
                    'timetable', ['class_id', 'day'], unique=False)
    op.create_index('ix_timetable_subject_id',
                    'timetable', ['subject_id'], unique=False)
    op.create_index('ix_timetable_start_time',
                    'timetable', ['start_time'], unique=False)


def downgrade():
    # notices
    op.drop_index('ix_notices_status_deleted',      table_name='notices')
    op.drop_index('ix_notices_posted_by',            table_name='notices')
    op.drop_index('ix_notices_target_role',          table_name='notices')
    op.drop_index('ix_notices_target_class_id',      table_name='notices')
    op.drop_index('ix_notices_created_at',           table_name='notices')
    # leaves
    op.drop_index('ix_leaves_student_id',            table_name='leave_applications')
    op.drop_index('ix_leaves_tg_status',             table_name='leave_applications')
    op.drop_index('ix_leaves_ct_status',             table_name='leave_applications')
    op.drop_index('ix_leaves_created_at',            table_name='leave_applications')
    op.drop_index('ix_leaves_start_date',            table_name='leave_applications')
    # assignments
    op.drop_index('ix_assignments_subject_id',       table_name='assignments')
    op.drop_index('ix_assignments_deadline',         table_name='assignments')
    op.drop_index('ix_assignments_created_by',       table_name='assignments')
    # grievances
    op.drop_index('ix_grievances_student_id',        table_name='grievances')
    op.drop_index('ix_grievances_status',            table_name='grievances')
    op.drop_index('ix_grievances_assigned_to',       table_name='grievances')
    op.drop_index('ix_grievances_created_at',        table_name='grievances')
    # certificates
    op.drop_index('ix_certificates_student_id',      table_name='certificates')
    op.drop_index('ix_certificates_status',          table_name='certificates')
    op.drop_index('ix_certificates_type',            table_name='certificates')
    # timetable
    op.drop_index('ix_timetable_class_day',          table_name='timetable')
    op.drop_index('ix_timetable_subject_id',         table_name='timetable')
    op.drop_index('ix_timetable_start_time',         table_name='timetable')
