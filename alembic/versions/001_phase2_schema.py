"""Phase 2 schema additions

Revision ID: 001_phase2
Revises:
Create Date: 2026-02-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001_phase2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Alter existing tables ---

    # proxies: add geo fields + allow 'degraded' status
    op.add_column("proxies", sa.Column("country_code", sa.String(2), nullable=True))
    op.add_column("proxies", sa.Column("city", sa.String(255), nullable=True))
    op.add_column("proxies", sa.Column("asn", sa.String(50), nullable=True))
    op.create_index("idx_proxies_country", "proxies", ["country_code"])
    # Drop old check constraint and add new one with 'degraded'
    op.drop_constraint("ck_proxy_health_status", "proxies", type_="check")
    op.create_check_constraint(
        "ck_proxy_health_status", "proxies",
        "last_health_status IN ('healthy', 'degraded', 'dead', 'unknown')"
    )

    # pools: add P2 config columns + allow new rotation strategies
    op.add_column("pools", sa.Column("is_exclusive", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("pools", sa.Column("sticky_session_ttl", sa.Integer(), server_default="0", nullable=False))
    op.add_column("pools", sa.Column("health_check_interval", sa.Integer(), server_default="60", nullable=False))
    op.add_column("pools", sa.Column("blacklist_threshold", sa.Float(), server_default="0.20", nullable=False))
    op.add_column("pools", sa.Column("blacklist_window_seconds", sa.Integer(), server_default="300", nullable=False))
    op.add_column("pools", sa.Column("blacklist_cooldown_seconds", sa.Integer(), server_default="1800", nullable=False))
    op.add_column("pools", sa.Column("min_healthy_proxies", sa.Integer(), server_default="1", nullable=False))
    op.drop_constraint("ck_pool_rotation_strategy", "pools", type_="check")
    op.create_check_constraint(
        "ck_pool_rotation_strategy", "pools",
        "rotation_strategy IN ('round_robin', 'random', 'weighted_random', 'least_connections')"
    )

    # pool_proxies: add weight
    op.add_column("pool_proxies", sa.Column("weight", sa.Integer(), server_default="1", nullable=False))
    op.create_check_constraint("ck_pool_proxy_weight", "pool_proxies", "weight > 0")

    # projects: add quotas
    op.add_column("projects", sa.Column("rate_limit_rpm", sa.Integer(), server_default="0", nullable=False))
    op.add_column("projects", sa.Column("bandwidth_quota_bytes", sa.BigInteger(), server_default="0", nullable=False))

    # providers: add API integration fields
    op.add_column("providers", sa.Column("api_endpoint", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("api_key_encrypted", sa.Text(), nullable=True))

    # --- Create new tables ---

    # project_proxy_blacklist
    op.create_table(
        "project_proxy_blacklist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proxy_id", UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_domain", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("auto_generated", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "proxy_id", "target_domain", name="uq_blacklist_project_proxy_domain"),
    )
    op.create_index("idx_blacklist_expires", "project_proxy_blacklist", ["expires_at"],
                     postgresql_where=sa.text("expires_at IS NOT NULL"))
    op.create_index("idx_blacklist_project", "project_proxy_blacklist", ["project_id"])

    # metrics_rollup
    op.create_table(
        "metrics_rollup",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(10), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_granularity", sa.String(10), nullable=False),
        sa.Column("total_requests", sa.Integer(), server_default="0"),
        sa.Column("successful_requests", sa.Integer(), server_default="0"),
        sa.Column("failed_requests", sa.Integer(), server_default="0"),
        sa.Column("bytes_sent", sa.BigInteger(), server_default="0"),
        sa.Column("bytes_received", sa.BigInteger(), server_default="0"),
        sa.Column("avg_response_time_ms", sa.Float(), nullable=True),
        sa.Column("p95_response_time_ms", sa.Float(), nullable=True),
        sa.UniqueConstraint("entity_type", "entity_id", "period_start", "period_granularity",
                            name="uq_metrics_rollup_entity_period"),
        sa.CheckConstraint("entity_type IN ('proxy', 'pool', 'project', 'provider')",
                           name="ck_metrics_entity_type"),
        sa.CheckConstraint("period_granularity IN ('5min', '1hour', '1day')",
                           name="ck_metrics_granularity"),
    )

    # alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("condition_config", JSONB(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_config", JSONB(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "condition_type IN ('error_rate_above', 'pool_below_min_healthy', "
            "'bandwidth_exceeded', 'all_proxies_dead')",
            name="ck_alert_condition_type"),
        sa.CheckConstraint("action_type IN ('webhook', 'auto_blacklist')",
                           name="ck_alert_action_type"),
    )

    # request_log (partitioned) - use raw SQL for partition support
    op.execute("""
        CREATE TABLE IF NOT EXISTS request_log (
            id BIGSERIAL,
            project_id UUID NOT NULL,
            pool_id UUID NOT NULL,
            proxy_id UUID NOT NULL,
            status_code SMALLINT,
            response_time_ms INTEGER,
            bytes_sent INTEGER DEFAULT 0,
            bytes_received INTEGER DEFAULT 0,
            target_domain VARCHAR(255),
            error_type VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_request_log_project ON request_log(project_id, created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_request_log_proxy ON request_log(proxy_id, created_at);")

    # Create initial partition for current month
    op.execute("""
        CREATE TABLE IF NOT EXISTS request_log_default PARTITION OF request_log DEFAULT;
    """)

    # health_check_log (partitioned)
    op.execute("""
        CREATE TABLE IF NOT EXISTS health_check_log (
            id BIGSERIAL,
            proxy_id UUID NOT NULL,
            status VARCHAR(30) NOT NULL,
            latency_ms INTEGER,
            external_ip VARCHAR(45),
            checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, checked_at)
        ) PARTITION BY RANGE (checked_at);
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_health_log_proxy ON health_check_log(proxy_id, checked_at);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS health_check_log_default PARTITION OF health_check_log DEFAULT;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS health_check_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS request_log CASCADE;")
    op.drop_table("alert_rules")
    op.drop_table("metrics_rollup")
    op.drop_table("project_proxy_blacklist")

    # Revert providers
    op.drop_column("providers", "api_key_encrypted")
    op.drop_column("providers", "api_endpoint")

    # Revert projects
    op.drop_column("projects", "bandwidth_quota_bytes")
    op.drop_column("projects", "rate_limit_rpm")

    # Revert pool_proxies
    op.drop_constraint("ck_pool_proxy_weight", "pool_proxies", type_="check")
    op.drop_column("pool_proxies", "weight")

    # Revert pools
    op.drop_column("pools", "min_healthy_proxies")
    op.drop_column("pools", "blacklist_cooldown_seconds")
    op.drop_column("pools", "blacklist_window_seconds")
    op.drop_column("pools", "blacklist_threshold")
    op.drop_column("pools", "health_check_interval")
    op.drop_column("pools", "sticky_session_ttl")
    op.drop_column("pools", "is_exclusive")
    op.drop_constraint("ck_pool_rotation_strategy", "pools", type_="check")
    op.create_check_constraint(
        "ck_pool_rotation_strategy", "pools",
        "rotation_strategy IN ('round_robin', 'random')"
    )

    # Revert proxies
    op.drop_index("idx_proxies_country", "proxies")
    op.drop_column("proxies", "asn")
    op.drop_column("proxies", "city")
    op.drop_column("proxies", "country_code")
    op.drop_constraint("ck_proxy_health_status", "proxies", type_="check")
    op.create_check_constraint(
        "ck_proxy_health_status", "proxies",
        "last_health_status IN ('healthy', 'dead', 'unknown')"
    )
