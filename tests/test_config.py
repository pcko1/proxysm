"""Tests for the Settings configuration class."""

import os
from unittest.mock import patch

import pytest

from src.config import Settings


class TestSettingsDefaults:
    def test_default_database_url(self):
        s = Settings()
        assert "postgresql+asyncpg://" in s.database_url

    def test_default_redis_url(self):
        s = Settings()
        assert s.redis_url.startswith("redis://")

    def test_default_log_level(self):
        s = Settings()
        assert s.pm_log_level == "info"

    def test_default_workers(self):
        s = Settings()
        assert s.pm_workers == 4

    def test_default_health_check_interval(self):
        s = Settings()
        assert s.health_check_interval == 60

    def test_default_prometheus_disabled(self):
        s = Settings()
        assert s.prometheus_enabled is False


class TestSettingsOverride:
    def test_explicit_values(self):
        s = Settings(
            database_url="postgresql+asyncpg://custom:custom@db:5432/custom",
            redis_url="redis://redis:6379/5",
            pm_log_level="debug",
            pm_workers=8,
            health_check_interval=120,
        )
        assert s.database_url == "postgresql+asyncpg://custom:custom@db:5432/custom"
        assert s.redis_url == "redis://redis:6379/5"
        assert s.pm_log_level == "debug"
        assert s.pm_workers == 8
        assert s.health_check_interval == 120

    @patch.dict(os.environ, {"PM_LOG_LEVEL": "warning"}, clear=False)
    def test_env_var_override(self):
        s = Settings()
        assert s.pm_log_level == "warning"


class TestSettingsTypes:
    def test_int_fields_are_int(self):
        s = Settings(pm_workers=2, health_check_interval=30)
        assert isinstance(s.pm_workers, int)
        assert isinstance(s.health_check_interval, int)

    def test_bool_field(self):
        s = Settings(prometheus_enabled=True)
        assert s.prometheus_enabled is True

    def test_all_health_fields(self):
        s = Settings(
            health_check_timeout=5,
            health_check_concurrency=100,
            health_failures_to_dead=5,
            health_failures_to_degraded=3,
            health_recoveries_to_healthy=4,
        )
        assert s.health_check_timeout == 5
        assert s.health_check_concurrency == 100
        assert s.health_failures_to_dead == 5
        assert s.health_failures_to_degraded == 3
        assert s.health_recoveries_to_healthy == 4
