"""add part_time_6h contract, is_overtime to entries, project_id nullable

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Aggiungi is_overtime a timesheet_entries
    op.add_column('timesheet_entries',
        sa.Column('is_overtime', sa.Boolean(), nullable=False, server_default='false')
    )
    # Rendi project_id nullable (per le righe straordinario)
    op.alter_column('timesheet_entries', 'project_id', nullable=True)
    # Aggiungi part_time_6h all'enum (Postgres)
    op.execute("ALTER TYPE contracttype ADD VALUE IF NOT EXISTS 'part_time_6h'")


def downgrade():
    op.drop_column('timesheet_entries', 'is_overtime')
    op.alter_column('timesheet_entries', 'project_id', nullable=False)
