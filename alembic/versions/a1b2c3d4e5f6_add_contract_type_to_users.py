"""add contract_type to users

Revision ID: a1b2c3d4e5f6
Revises: 8b403797a913
Create Date: 2026-04-24 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8b403797a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE contracttype AS ENUM ('full_time', 'part_time')")
    op.add_column('users', sa.Column(
        'contract_type',
        sa.Enum('full_time', 'part_time', name='contracttype'),
        nullable=False,
        server_default='full_time',
    ))


def downgrade() -> None:
    op.drop_column('users', 'contract_type')
    op.execute("DROP TYPE contracttype")
