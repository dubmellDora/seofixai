"""add user_sessions (S1-03a)

Revision ID: b2d6f1c8e402
Revises: a1c5e0b7d301
Create Date: 2026-11-16

Server-side sessions. Additive only: a new table, nothing existing changes.

  token_hash UNIQUE          - lookup by the cookie token's sha256; no raw token stored
  ix_user_sessions_user_id   - "revoke all sessions of user X" without a scan
  ck_user_sessions_host_kind - only 'app' or 'admin'
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d6f1c8e402"
down_revision: Union[str, Sequence[str], None] = "a1c5e0b7d301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("csrf_token", sa.String(), nullable=False),
        sa.Column("host_kind", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("host_kind IN ('app', 'admin')", name="ck_user_sessions_host_kind"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
