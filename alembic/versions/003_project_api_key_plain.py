"""Add plaintext api_key column to projects

Revision ID: 003_api_key_plain
Revises: 002_provider_to_text
"""
from alembic import op
import sqlalchemy as sa

revision = "003_api_key_plain"
down_revision = "002_provider_to_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("api_key_plain", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "api_key_plain")
