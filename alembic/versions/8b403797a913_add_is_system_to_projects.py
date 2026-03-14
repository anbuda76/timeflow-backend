"""add is_system to projects
Revision ID: 8b403797a913
Revises: ac911447a50f
Create Date: 2026-03-14 08:52:20.200227
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '8b403797a913'
down_revision: Union[str, None] = 'ac911447a50f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('projects', sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'))

def downgrade() -> None:
    op.drop_column('projects', 'is_system')