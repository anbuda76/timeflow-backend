"""add note to projects

Revision ID: 9f2a1d4c6b21
Revises: 3ad871e8c394
Create Date: 2026-03-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f2a1d4c6b21"
down_revision: Union[str, None] = "3ad871e8c394"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "note")

