"""Drop blacklist table and pool blacklist columns

Revision ID: 004_drop_blacklist
Revises: 003_api_key_plain
"""
from alembic import op

revision = "004_drop_blacklist"
down_revision = "003_api_key_plain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("project_proxy_blacklist")
    op.drop_column("pools", "blacklist_threshold")
    op.drop_column("pools", "blacklist_window_seconds")
    op.drop_column("pools", "blacklist_cooldown_seconds")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column("pools", sa.Column("blacklist_cooldown_seconds", sa.Integer(), server_default="1800", nullable=True))
    op.add_column("pools", sa.Column("blacklist_window_seconds", sa.Integer(), server_default="300", nullable=True))
    op.add_column("pools", sa.Column("blacklist_threshold", sa.Float(), server_default="0.20", nullable=True))
    op.create_table(
        "project_proxy_blacklist",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proxy_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_domain", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("auto_generated", sa.Boolean(), server_default="true"),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "proxy_id", "target_domain", name="uq_blacklist_project_proxy_domain"),
    )
