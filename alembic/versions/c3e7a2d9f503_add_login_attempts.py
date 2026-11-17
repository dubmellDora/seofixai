"""add login_attempts (S1-03d)

Revision ID: c3e7a2d9f503
Revises: b2d6f1c8e402
Create Date: 2026-11-16

Failed-login log used for rate limiting. Additive only. Email is stored as a
SHA-256 hash. Three indexes because the throttle queries by email_hash, by ip,
and by created_at (sliding window + cleanup).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e7a2d9f503"
down_revision: Union[str, Sequence[str], None] = "b2d6f1c8e402"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_hash", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_attempts_email_hash", "login_attempts", ["email_hash"])
    op.create_index("ix_login_attempts_ip", "login_attempts", ["ip"])
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_login_attempts_created_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip", table_name="login_attempts")
    op.drop_index("ix_login_attempts_email_hash", table_name="login_attempts")
    op.drop_table("login_attempts")
