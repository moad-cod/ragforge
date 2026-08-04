"""expand embedding run progress

Revision ID: 20260803_0003
Revises: 20260713_0002
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0003"
down_revision: Union[str, None] = "20260713_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_EMBEDDING_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
NEW_EMBEDDING_STATUSES = (
    "queued",
    "loading_model",
    "running",
    "retrying",
    "completed",
    "failed",
    "cancelled",
)


def _status_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.add_column("embedding_runs", sa.Column("total_batches", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("embedding_runs", sa.Column("embedded_batches", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("embedding_runs", sa.Column("batch_size", sa.Integer(), nullable=True))
    op.add_column("embedding_runs", sa.Column("embedding_backend", sa.String(), nullable=True))
    op.add_column("embedding_runs", sa.Column("embedding_device", sa.String(), nullable=True))
    op.add_column("embedding_runs", sa.Column("embedding_dimension", sa.Integer(), nullable=True))
    op.add_column("embedding_runs", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("embedding_runs", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("embedding_runs", sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column("embedding_runs", sa.Column("error_code", sa.String(), nullable=True))
    op.drop_constraint("ck_embedding_runs_status", "embedding_runs", type_="check")
    op.create_check_constraint(
        "ck_embedding_runs_status",
        "embedding_runs",
        _status_check("status", NEW_EMBEDDING_STATUSES),
    )


def downgrade() -> None:
    op.drop_constraint("ck_embedding_runs_status", "embedding_runs", type_="check")
    op.create_check_constraint(
        "ck_embedding_runs_status",
        "embedding_runs",
        _status_check("status", OLD_EMBEDDING_STATUSES),
    )
    op.drop_column("embedding_runs", "error_code")
    op.drop_column("embedding_runs", "last_heartbeat_at")
    op.drop_column("embedding_runs", "updated_at")
    op.drop_column("embedding_runs", "attempt")
    op.drop_column("embedding_runs", "embedding_dimension")
    op.drop_column("embedding_runs", "embedding_device")
    op.drop_column("embedding_runs", "embedding_backend")
    op.drop_column("embedding_runs", "batch_size")
    op.drop_column("embedding_runs", "embedded_batches")
    op.drop_column("embedding_runs", "total_batches")
