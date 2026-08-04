"""allow duplicate chunk content hashes

Revision ID: 20260803_0004
Revises: 20260803_0003
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260803_0004"
down_revision: Union[str, None] = "20260803_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_chunks_version_content_hash", "chunks", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_chunks_version_content_hash",
        "chunks",
        ["document_version_id", "content_hash"],
    )
