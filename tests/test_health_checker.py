"""Tests for src.health.checker module."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.health.checker import _parse_external_ip, _schedule_next_check, check_single_proxy


# ---------------------------------------------------------------------------
# _parse_external_ip
# ---------------------------------------------------------------------------

class TestParseExternalIp:
    def test_valid_origin(self):
        body = json.dumps({"origin": "1.2.3.4"}).encode()
        assert _parse_external_ip(body) == "1.2.3.4"

    def test_comma_separated_takes_first(self):
        body = json.dumps({"origin": "5.6.7.8, 9.10.11.12"}).encode()
        assert _parse_external_ip(body) == "5.6.7.8"

    def test_missing_origin_key_returns_none(self):
        body = json.dumps({"ip": "1.2.3.4"}).encode()
        # origin defaults to "", split/strip yields "", which is falsy -> None
        assert _parse_external_ip(body) is None

    def test_empty_json_object_returns_none(self):
        body = b"{}"
        assert _parse_external_ip(body) is None

    def test_invalid_json_returns_none(self):
        body = b"not json at all"
        assert _parse_external_ip(body) is None

    def test_empty_bytes_returns_none(self):
        body = b""
        assert _parse_external_ip(body) is None

    def test_origin_empty_string_returns_none(self):
        body = json.dumps({"origin": ""}).encode()
        assert _parse_external_ip(body) is None


# ---------------------------------------------------------------------------
# _schedule_next_check
# ---------------------------------------------------------------------------

class TestScheduleNextCheck:
    @pytest.mark.asyncio
    async def test_healthy_uses_base_plus_jitter(self):
        redis = AsyncMock()
        with patch("src.health.checker.settings") as mock_settings:
            mock_settings.health_check_interval = 60
            now = time.time()
            await _schedule_next_check(redis, "p1", "healthy")
        redis.set.assert_awaited_once()
        args, kwargs = redis.set.await_args
        assert args[0] == "proxy:p1:next_check"
        ts = float(args[1])
        # healthy: base(60) + uniform(0, 15) => 60..75 from now
        assert now + 59 < ts < now + 80
        # ex should be interval + 60
        assert kwargs.get("ex") is not None

    @pytest.mark.asyncio
    async def test_degraded_uses_short_interval(self):
        redis = AsyncMock()
        with patch("src.health.checker.settings") as mock_settings:
            mock_settings.health_check_interval = 60
            now = time.time()
            await _schedule_next_check(redis, "p2", "degraded")
        args, kwargs = redis.set.await_args
        ts = float(args[1])
        # degraded: 15 + uniform(0, 5) => 15..20 from now
        assert now + 14 < ts < now + 25

    @pytest.mark.asyncio
    async def test_dead_reads_backoff_from_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"240")
        with patch("src.health.checker.settings") as mock_settings:
            mock_settings.health_check_interval = 60
            now = time.time()
            await _schedule_next_check(redis, "p3", "dead")
        redis.get.assert_awaited_once_with("proxy:p3:dead_backoff")
        args, _ = redis.set.await_args
        ts = float(args[1])
        assert now + 239 < ts < now + 245

    @pytest.mark.asyncio
    async def test_dead_defaults_backoff_120(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        with patch("src.health.checker.settings") as mock_settings:
            mock_settings.health_check_interval = 60
            now = time.time()
            await _schedule_next_check(redis, "p4", "dead")
        args, _ = redis.set.await_args
        ts = float(args[1])
        assert now + 119 < ts < now + 125

    @pytest.mark.asyncio
    async def test_unknown_uses_base_interval(self):
        redis = AsyncMock()
        with patch("src.health.checker.settings") as mock_settings:
            mock_settings.health_check_interval = 60
            now = time.time()
            await _schedule_next_check(redis, "p5", "unknown")
        args, _ = redis.set.await_args
        ts = float(args[1])
        assert now + 59 < ts < now + 65


# ---------------------------------------------------------------------------
# Helpers for check_single_proxy tests
# ---------------------------------------------------------------------------

def _make_proxy(proxy_id="proxy1", host="1.2.3.4", port=8080, protocol="http",
                username=None, password=None, last_health_status=None,
                avg_latency_ms=None):
    """Create a mock Proxy ORM object."""
    proxy = MagicMock()
    proxy.id = proxy_id
    proxy.host = host
    proxy.port = port
    proxy.protocol = protocol
    proxy.username = username
    proxy.password_encrypted = password
    proxy.last_health_status = last_health_status
    proxy.avg_latency_ms = avg_latency_ms
    return proxy


def _mock_aiohttp_success(body=b'{"origin": "5.5.5.5"}'):
    """Return a mock that replaces aiohttp.ClientSession for a successful request."""
    resp = MagicMock()
    resp.read = AsyncMock(return_value=body)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=resp)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _mock_aiohttp_failure(exc=None):
    """Return a mock that replaces aiohttp.ClientSession to raise on .get()."""
    if exc is None:
        exc = Exception("connection refused")

    session = MagicMock()
    session.get = MagicMock(side_effect=exc)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _settings_patch():
    return patch("src.health.checker.settings", **{
        "health_check_url": "http://httpbin.org/ip",
        "health_check_timeout": 10,
        "health_check_interval": 60,
        "health_failures_to_dead": 3,
        "health_failures_to_degraded": 2,
        "health_recoveries_to_healthy": 3,
        "prometheus_enabled": False,
    })


# ---------------------------------------------------------------------------
# check_single_proxy — success paths
# ---------------------------------------------------------------------------

class TestCheckSingleProxySuccess:
    @pytest.mark.asyncio
    async def test_unknown_to_healthy(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        proxy = _make_proxy(last_health_status=None)  # defaults to "unknown"

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            new_status, latency, ip = await check_single_proxy(proxy)

        assert new_status == "healthy"
        assert latency >= 0
        assert ip == "5.5.5.5"
        # Failure counter reset on success
        redis.delete.assert_any_await("proxy:proxy1:failures")

    @pytest.mark.asyncio
    async def test_dead_to_degraded(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.set = AsyncMock()
        proxy = _make_proxy(last_health_status="dead")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            new_status, latency, ip = await check_single_proxy(proxy)

        assert new_status == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_stays_degraded_until_3_successes(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=2)  # only 2 successes
        proxy = _make_proxy(last_health_status="degraded")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_to_healthy_after_3_successes(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=3)
        proxy = _make_proxy(last_health_status="degraded")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "healthy"

    @pytest.mark.asyncio
    async def test_healthy_stays_healthy(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        proxy = _make_proxy(last_health_status="healthy", avg_latency_ms=100)

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "healthy"

    @pytest.mark.asyncio
    async def test_success_resets_failure_counter(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        proxy = _make_proxy(last_health_status=None)

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            await check_single_proxy(proxy)

        redis.delete.assert_any_await("proxy:proxy1:failures")

    @pytest.mark.asyncio
    async def test_success_resets_dead_backoff(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        proxy = _make_proxy(last_health_status="dead")
        redis.set = AsyncMock()

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_success()):
            await check_single_proxy(proxy)

        redis.delete.assert_any_await("proxy:proxy1:dead_backoff")


# ---------------------------------------------------------------------------
# check_single_proxy — failure paths
# ---------------------------------------------------------------------------

class TestCheckSingleProxyFailure:
    @pytest.mark.asyncio
    async def test_unknown_to_degraded(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        proxy = _make_proxy(last_health_status=None)

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, latency, ip = await check_single_proxy(proxy)

        assert new_status == "degraded"
        assert latency == 0.0
        assert ip is None

    @pytest.mark.asyncio
    async def test_healthy_stays_healthy_after_1_failure(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)  # only 1 failure, threshold is 2
        proxy = _make_proxy(last_health_status="healthy")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "healthy"

    @pytest.mark.asyncio
    async def test_healthy_to_degraded_after_2_failures(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=2)
        proxy = _make_proxy(last_health_status="healthy")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_to_dead_after_3_failures(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=3)
        proxy = _make_proxy(last_health_status="degraded")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "dead"

    @pytest.mark.asyncio
    async def test_degraded_stays_degraded_under_threshold(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=2)  # under threshold of 3
        proxy = _make_proxy(last_health_status="degraded")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "degraded"

    @pytest.mark.asyncio
    async def test_dead_stays_dead_with_exponential_backoff(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=10)
        redis.get = AsyncMock(return_value=b"120")
        redis.set = AsyncMock()
        proxy = _make_proxy(last_health_status="dead")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "dead"
        # Should double backoff: 120 -> 240
        redis.set.assert_any_await("proxy:proxy1:dead_backoff", "240", ex=3600)

    @pytest.mark.asyncio
    async def test_dead_backoff_capped_at_600(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=10)
        redis.get = AsyncMock(return_value=b"480")
        redis.set = AsyncMock()
        proxy = _make_proxy(last_health_status="dead")

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            new_status, _, _ = await check_single_proxy(proxy)

        assert new_status == "dead"
        # 480 * 2 = 960, capped to 600
        redis.set.assert_any_await("proxy:proxy1:dead_backoff", "600", ex=3600)

    @pytest.mark.asyncio
    async def test_failure_resets_success_counter(self):
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        proxy = _make_proxy(last_health_status=None)

        with _settings_patch(), \
             patch("src.health.checker.get_redis", AsyncMock(return_value=redis)), \
             patch("src.health.checker.aiohttp.ClientSession", return_value=_mock_aiohttp_failure()):
            await check_single_proxy(proxy)

        redis.delete.assert_any_await("proxy:proxy1:successes")
