import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings


@pytest.fixture
def mock_settings():
    """Create test settings without touching real env vars."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/1",
        pm_secret_key="test-secret",
        pm_admin_password="testpassword",
        pm_log_level="debug",
        health_check_interval=60,
        health_check_timeout=10,
        health_failures_to_dead=3,
        health_failures_to_degraded=2,
        health_recoveries_to_healthy=3,
        prometheus_enabled=False,
    )


@pytest.fixture
def admin_token():
    """Return the admin password for test auth."""
    return "testpassword"


@pytest.fixture
def admin_auth_header(admin_token):
    """Return Authorization header with admin token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with common async methods."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.hset = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.pipeline = MagicMock()
    pipe = AsyncMock()
    pipe.delete = MagicMock()
    pipe.rpush = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline.return_value = pipe
    redis.register_script = MagicMock(return_value=AsyncMock())
    return redis


@pytest.fixture
def sample_proxy_data():
    """Return sample proxy data for tests."""
    return {
        "id": uuid.uuid4(),
        "host": "192.168.1.1",
        "port": 8080,
        "protocol": "http",
        "username": "user1",
        "password_encrypted": "pass1",
        "is_active": True,
        "last_health_status": "unknown",
        "avg_latency_ms": None,
    }


@pytest.fixture
def sample_proxy(sample_proxy_data):
    """Create a mock Proxy object."""
    proxy = MagicMock()
    for key, value in sample_proxy_data.items():
        setattr(proxy, key, value)
    return proxy
