"""Initial schema — complete database setup

Revision ID: 001_initial
Revises:
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── proxies ──────────────────────────────────────────────────────────
    op.create_table(
        "proxies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(255), nullable=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(10), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_status", sa.String(20), server_default="unknown", nullable=False),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("asn", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("host", "port", "protocol", name="uq_proxy_host_port_protocol"),
        sa.CheckConstraint("port >= 0 AND port <= 65535", name="ck_proxy_port_range"),
        sa.CheckConstraint("protocol IN ('http', 'https', 'socks5')", name="ck_proxy_protocol"),
        sa.CheckConstraint(
            "last_health_status IN ('healthy', 'degraded', 'dead', 'unknown')",
            name="ck_proxy_health_status",
        ),
    )
    op.create_index("idx_proxies_country", "proxies", ["country_code"])

    # ── pools ────────────────────────────────────────────────────────────
    op.create_table(
        "pools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("rotation_strategy", sa.String(30), server_default="round_robin", nullable=False),
        sa.Column("is_exclusive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sticky_session_ttl", sa.Integer(), server_default="0", nullable=False),
        sa.Column("health_check_interval", sa.Integer(), server_default="60", nullable=False),
        sa.Column("min_healthy_proxies", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "rotation_strategy IN ('round_robin', 'random', 'weighted_random', 'least_connections')",
            name="ck_pool_rotation_strategy",
        ),
    )

    # ── pool_proxies (junction) ──────────────────────────────────────────
    op.create_table(
        "pool_proxies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pool_id", UUID(as_uuid=True), sa.ForeignKey("pools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proxy_id", UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("weight", sa.Integer(), server_default="1", nullable=False),
        sa.UniqueConstraint("pool_id", "proxy_id", name="uq_pool_proxy"),
        sa.CheckConstraint("weight > 0", name="ck_pool_proxy_weight"),
    )

    # ── projects ─────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key_hash", sa.String(128), nullable=False),
        sa.Column("api_key_plain", sa.String(255), nullable=True),
        sa.Column("rate_limit_rpm", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bandwidth_quota_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── project_pools (junction) ─────────────────────────────────────────
    op.create_table(
        "project_pools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pool_id", UUID(as_uuid=True), sa.ForeignKey("pools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "pool_id", name="uq_project_pool"),
    )

    # ── metrics_rollup ───────────────────────────────────────────────────
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
        sa.UniqueConstraint(
            "entity_type", "entity_id", "period_start", "period_granularity",
            name="uq_metrics_rollup_entity_period",
        ),
        sa.CheckConstraint(
            "entity_type IN ('proxy', 'pool', 'project', 'provider')",
            name="ck_metrics_entity_type",
        ),
        sa.CheckConstraint(
            "period_granularity IN ('5min', '1hour', '1day')",
            name="ck_metrics_granularity",
        ),
    )

    # ── alert_rules ──────────────────────────────────────────────────────
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
            name="ck_alert_condition_type",
        ),
        sa.CheckConstraint("action_type IN ('webhook')", name="ck_alert_action_type"),
    )

    # ── request_log (partitioned by created_at) ──────────────────────────
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
    op.execute("CREATE TABLE IF NOT EXISTS request_log_default PARTITION OF request_log DEFAULT;")

    # ── health_check_log (partitioned by checked_at) ─────────────────────
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
    op.execute("CREATE TABLE IF NOT EXISTS health_check_log_default PARTITION OF health_check_log DEFAULT;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS health_check_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS request_log CASCADE;")
    op.drop_table("alert_rules")
    op.drop_table("metrics_rollup")
    op.drop_table("project_pools")
    op.drop_table("projects")
    op.drop_table("pool_proxies")
    op.drop_table("pools")
    op.drop_table("proxies")
