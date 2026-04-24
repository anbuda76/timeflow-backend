"""add contract_type to users

Revision ID: a1b2c3d4e5f6
Revises: 9f2a1d4c6b21
Create Date: 2026-04-24 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9f2a1d4c6b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crea il tipo enum solo se non esiste già
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE contracttype AS ENUM ('full_time', 'part_time');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    # Aggiunge la colonna solo se non esiste già
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS contract_type contracttype NOT NULL DEFAULT 'full_time';
    """)


def downgrade() -> None:
    op.drop_column('users', 'contract_type')
    op.execute("DROP TYPE IF EXISTS contracttype")
