"""add agencies and users (S1-01)

Revision ID: a1c5e0b7d301
Revises: e9d001b85a1c
Create Date: 2026-11-15

Adds the two account tables. Nothing existing is changed: no column is added to
projects yet (that is the tenancy migration), so the running app behaves
exactly as before.

Constraints, and why each exists:
  agencies.slug UNIQUE                 - one url-safe name per agency
  ck_agencies_slug_lowercase           - slugs are stored lowercase
  users.email UNIQUE                   - one account per email
  ck_users_email_lowercase             - the database refuses un-normalized emails
  ck_users_platform_role / agency_role - only the approved role values (D-011)
  ck_users_customer_has_agency         - a customer always has an agency + role
  ix_users_agency_id                   - "all users of agency X" without a scan
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c5e0b7d301"
down_revision: Union[str, Sequence[str], None] = "e9d001b85a1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("brand_color", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("slug = lower(slug)", name="ck_agencies_slug_lowercase"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("platform_role", sa.String(), nullable=False),
        sa.Column("agency_role", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.CheckConstraint(
            "platform_role IN ('customer', 'platform_admin', 'support_admin')",
            name="ck_users_platform_role",
        ),
        sa.CheckConstraint(
            "agency_role IS NULL OR agency_role IN ('owner', 'member')",
            name="ck_users_agency_role",
        ),
        sa.CheckConstraint(
            "platform_role <> 'customer' OR (agency_id IS NOT NULL AND agency_role IS NOT NULL)",
            name="ck_users_customer_has_agency",
        ),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_agency_id", "users", ["agency_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_agency_id", table_name="users")
    op.drop_table("users")
    op.drop_table("agencies")
