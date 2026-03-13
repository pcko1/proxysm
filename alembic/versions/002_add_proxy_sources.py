"""Add proxy_sources table and source_id FK on proxies

Revision ID: 002_proxy_sources
Revises: 001_initial
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002_proxy_sources"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── proxy_sources ────────────────────────────────────────────────────
    op.create_table(
        "proxy_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('url', 'file', 'manual')",
            name="ck_proxy_source_type",
        ),
    )

    # ── Add source_id FK to proxies ──────────────────────────────────────
    op.add_column(
        "proxies",
        sa.Column(
            "source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("proxy_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("idx_proxies_source_id", "proxies", ["source_id"])


def downgrade() -> None:
    op.drop_index("idx_proxies_source_id", table_name="proxies")
    op.drop_column("proxies", "source_id")
    op.drop_table("proxy_sources")
