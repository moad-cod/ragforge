"""add durable query answer

Revision ID: 20260713_0002
Revises: 20260711_0001
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0002"
down_revision: Union[str, None] = "20260711_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("query_logs", sa.Column("answer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("query_logs", "answer")
