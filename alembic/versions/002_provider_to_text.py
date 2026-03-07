"""Demote provider from entity to text label on proxies

Revision ID: 002_provider_to_text
Revises: 001_phase2
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002_provider_to_text"
down_revision = "001_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxies", sa.Column("provider", sa.String(255), nullable=True))
    op.execute("""
        UPDATE proxies
        SET provider = providers.name
        FROM providers
        WHERE proxies.provider_id = providers.id
    """)
    op.drop_constraint("proxies_provider_id_fkey", "proxies", type_="foreignkey")
    op.drop_index("idx_proxies_provider", "proxies", if_exists=True)
    op.drop_column("proxies", "provider_id")
    op.drop_table("providers")


def downgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("api_endpoint", sa.Text(), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("proxies", sa.Column("provider_id", UUID(as_uuid=True), nullable=True))
    op.create_index("idx_proxies_provider", "proxies", ["provider_id"])
    op.drop_column("proxies", "provider")
