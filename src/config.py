from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://proxymanager:changeme@localhost:5432/proxymanager"
    redis_url: str = "redis://localhost:6379/0"
    pm_secret_key: str = "change-me"
    pm_admin_password: str = "changeme"
    pm_log_level: str = "info"
    pm_workers: int = 4

    # Proxy server ports
    proxy_http_port: int = 9080
    proxy_socks5_port: int = 9081

    # Health check defaults
    health_check_interval: int = 60
    health_check_timeout: int = 10
    health_check_concurrency: int = 200
    health_check_url: str = "http://httpbin.org/ip"

    # Health status thresholds
    health_failures_to_dead: int = 3
    health_failures_to_degraded: int = 2
    health_recoveries_to_healthy: int = 3

    # Phase 2: Metrics
    metrics_rollup_interval: int = 300
    bandwidth_flush_interval: int = 30
    request_log_retention_days: int = 7
    metrics_5min_retention_days: int = 7
    metrics_1hour_retention_days: int = 90

    # Phase 2: Rate limiting
    rate_limit_window_seconds: int = 60

    # Source polling
    source_poll_interval: int = 3600

    # Alert evaluation
    alert_check_interval: int = 60
    alert_cooldown_seconds: int = 900

    # Prometheus metrics
    prometheus_enabled: bool = False
    prometheus_port: int = 0  # 0 = serve on main HTTP port at /metrics

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
