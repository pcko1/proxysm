"""Tests for src.rotation.engine module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, call

from src.rotation.engine import RotationEngine, PoolExhaustedError


@pytest.fixture
def mock_redis():
    """Create a mock Redis instance with register_script returning AsyncMock callables."""
    redis = AsyncMock()
    redis.register_script = MagicMock(return_value=AsyncMock(return_value=None))
    return redis


@pytest.fixture
def engine(mock_redis):
    return RotationEngine(mock_redis)


# ---------------------------------------------------------------------------
# get_next_proxy — strategy dispatch
# ---------------------------------------------------------------------------

class TestGetNextProxy:
    @pytest.mark.asyncio
    async def test_round_robin_returns_proxy(self, engine, mock_redis):
        engine._rr_script = AsyncMock(return_value=b"proxy1")
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "1.2.3.4", "port": "8080", "protocol": "http",
            "username": "", "password": "",
        })

        result = await engine.get_next_proxy("pool1", strategy="round_robin")
        assert result["id"] == "proxy1"
        assert result["host"] == "1.2.3.4"
        assert result["port"] == 8080

    @pytest.mark.asyncio
    async def test_random_strategy(self, engine, mock_redis):
        engine._rand_script = AsyncMock(return_value=b"proxy2")
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "5.6.7.8", "port": "3128", "protocol": "https",
            "username": "user", "password": "pass",
        })

        result = await engine.get_next_proxy("pool1", strategy="random")
        assert result["id"] == "proxy2"
        assert result["protocol"] == "https"

    @pytest.mark.asyncio
    async def test_weighted_random_strategy(self, engine, mock_redis):
        engine._weighted_script = AsyncMock(return_value=b"proxy3")
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "10.0.0.1", "port": "9090", "protocol": "socks5",
            "username": "", "password": "",
        })

        result = await engine.get_next_proxy("pool1", strategy="weighted_random")
        assert result["id"] == "proxy3"
        assert result["protocol"] == "socks5"

    @pytest.mark.asyncio
    async def test_least_connections_strategy(self, engine, mock_redis):
        engine._lc_script = AsyncMock(return_value=b"proxy4")
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "10.0.0.2", "port": "1080", "protocol": "http",
            "username": "", "password": "",
        })

        result = await engine.get_next_proxy("pool1", strategy="least_connections")
        assert result["id"] == "proxy4"

    @pytest.mark.asyncio
    async def test_pool_exhausted_when_lua_returns_none(self, engine):
        engine._rr_script = AsyncMock(return_value=None)

        with pytest.raises(PoolExhaustedError):
            await engine.get_next_proxy("pool_empty", strategy="round_robin")

    @pytest.mark.asyncio
    async def test_username_empty_string_becomes_none(self, engine, mock_redis):
        engine._rr_script = AsyncMock(return_value=b"px")
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "1.1.1.1", "port": "80", "protocol": "http",
            "username": "", "password": "",
        })

        result = await engine.get_next_proxy("pool1")
        assert result["username"] is None
        assert result["password"] is None


# ---------------------------------------------------------------------------
# Sticky sessions
# ---------------------------------------------------------------------------

class TestStickySessions:
    @pytest.mark.asyncio
    async def test_sticky_hit_returns_cached_proxy(self, engine, mock_redis):
        """When a sticky proxy exists and is not dead, return it."""
        mock_redis.get = AsyncMock(side_effect=lambda k:
            "sticky_px" if k.startswith("sticky:") else "healthy"
        )
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "2.2.2.2", "port": "8080", "protocol": "http",
            "username": "", "password": "",
        })

        result = await engine.get_next_proxy(
            "pool1", strategy="round_robin", session_key="sess123"
        )
        assert result["id"] == "sticky_px"

    @pytest.mark.asyncio
    async def test_sticky_miss_falls_through_to_rotation(self, engine, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        engine._rr_script = AsyncMock(return_value=b"fallback_px")
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "3.3.3.3", "port": "8080", "protocol": "http",
            "username": "", "password": "",
        })

        result = await engine.get_next_proxy(
            "pool1", strategy="round_robin", session_key="sess_miss"
        )
        assert result["id"] == "fallback_px"

    @pytest.mark.asyncio
    async def test_set_sticky_session(self, engine, mock_redis):
        await engine.set_sticky_session("pool1", "sess_abc", "proxy99", ttl=600)
        mock_redis.set.assert_awaited_once_with(
            "sticky:pool1:sess_abc", "proxy99", ex=600
        )


# ---------------------------------------------------------------------------
# _build_proxy_dict
# ---------------------------------------------------------------------------

class TestBuildProxyDict:
    @pytest.mark.asyncio
    async def test_returns_dict_from_redis_hash(self, engine, mock_redis):
        mock_redis.hgetall = AsyncMock(return_value={
            "host": "10.0.0.1", "port": "3128", "protocol": "http",
            "username": "admin", "password": "secret",
        })

        result = await engine._build_proxy_dict("px1", "pool1")
        assert result["id"] == "px1"
        assert result["host"] == "10.0.0.1"
        assert result["port"] == 3128
        assert result["username"] == "admin"
        assert result["password"] == "secret"

    @pytest.mark.asyncio
    async def test_raises_pool_exhausted_when_info_missing(self, engine, mock_redis):
        mock_redis.hgetall = AsyncMock(return_value={})

        with pytest.raises(PoolExhaustedError):
            await engine._build_proxy_dict("px_gone", "pool1")


# ---------------------------------------------------------------------------
# sync_pool / sync_weighted_pool
# ---------------------------------------------------------------------------

class TestSyncPool:
    @pytest.mark.asyncio
    async def test_sync_pool_rebuilds_list(self, engine, mock_redis):
        pipe = AsyncMock()
        pipe.delete = MagicMock()
        pipe.rpush = MagicMock()
        pipe.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=pipe)

        await engine.sync_pool("pool1", ["p1", "p2", "p3"])
        pipe.delete.assert_called_once_with("pool:pool1:proxies")
        pipe.rpush.assert_called_once_with("pool:pool1:proxies", "p1", "p2", "p3")
        pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_pool_empty_list_skips_rpush(self, engine, mock_redis):
        pipe = AsyncMock()
        pipe.delete = MagicMock()
        pipe.rpush = MagicMock()
        pipe.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=pipe)

        await engine.sync_pool("pool1", [])
        pipe.delete.assert_called_once_with("pool:pool1:proxies")
        pipe.rpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_weighted_pool_rebuilds_zset(self, engine, mock_redis):
        pipe = AsyncMock()
        pipe.delete = MagicMock()
        pipe.zadd = MagicMock()
        pipe.execute = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=pipe)

        weights = {"p1": 10, "p2": 5, "p3": 1}
        await engine.sync_weighted_pool("pool1", weights)
        pipe.delete.assert_called_once_with("pool:pool1:weighted")
        pipe.zadd.assert_called_once_with(
            "pool:pool1:weighted", {"p1": 10, "p2": 5, "p3": 1}
        )
        pipe.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_proxy_health / cache_proxy_info
# ---------------------------------------------------------------------------

class TestProxyStateManagement:
    @pytest.mark.asyncio
    async def test_update_proxy_health_sets_with_ttl(self, engine, mock_redis):
        await engine.update_proxy_health("px1", "degraded")
        mock_redis.set.assert_awaited_once_with(
            "proxy:px1:health", "degraded", ex=120
        )

    @pytest.mark.asyncio
    async def test_cache_proxy_info_sets_hash(self, engine, mock_redis):
        info = {"host": "1.1.1.1", "port": 8080, "protocol": "http"}
        await engine.cache_proxy_info("px1", info)
        mock_redis.hset.assert_awaited_once()
        call_args = mock_redis.hset.await_args
        assert call_args[0][0] == "proxy:px1:info"
        mapping = call_args[1]["mapping"]
        assert mapping["host"] == "1.1.1.1"
        assert mapping["port"] == "8080"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_allowed(self, engine):
        engine._rate_limit_script = AsyncMock(return_value=1)

        allowed = await engine.check_rate_limit("proj1", rpm_limit=100)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, engine):
        engine._rate_limit_script = AsyncMock(return_value=0)

        allowed = await engine.check_rate_limit("proj1", rpm_limit=100)
        assert allowed is False


# ---------------------------------------------------------------------------
# Connection tracking
# ---------------------------------------------------------------------------

class TestConnectionTracking:
    @pytest.mark.asyncio
    async def test_track_connection_increment(self, engine, mock_redis):
        await engine.track_connection("pool1", "px1", increment=True)
        mock_redis.zincrby.assert_awaited_once_with(
            "pool:pool1:connections", 1, "px1"
        )

    @pytest.mark.asyncio
    async def test_track_connection_decrement(self, engine, mock_redis):
        await engine.track_connection("pool1", "px1", increment=False)
        mock_redis.zincrby.assert_awaited_once_with(
            "pool:pool1:connections", -1, "px1"
        )
