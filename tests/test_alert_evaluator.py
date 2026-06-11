"""Tests for the alert evaluator (src/services/alerts.py)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.alerts import (
    _check_all_dead,
    _check_bandwidth,
    _check_error_rate,
    _check_pool_health,
    _fire_webhook,
    evaluate_alerts,
)


def _db_returning_one(row):
    """AsyncMock db whose execute().one() returns *row*."""
    db = AsyncMock()
    result = MagicMock()
    result.one.return_value = row
    db.execute.return_value = result
    return db


def _db_returning_all(rows):
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute.return_value = result
    return db


# ---------------------------------------------------------------------------
# error_rate_above
# ---------------------------------------------------------------------------


async def test_error_rate_triggers_above_threshold():
    db = _db_returning_one((100, 60))  # total=100, ok=60 -> 40% errors
    ctx = await _check_error_rate(db, {"threshold": 0.2, "window_seconds": 300})
    assert ctx is not None
    assert ctx["actual"] == 0.4
    assert ctx["threshold"] == 0.2
    assert ctx["requests"] == 100


async def test_error_rate_quiet_below_threshold():
    db = _db_returning_one((100, 95))  # 5% errors
    assert await _check_error_rate(db, {"threshold": 0.2}) is None


async def test_error_rate_quiet_with_no_traffic():
    db = _db_returning_one((0, 0))
    assert await _check_error_rate(db, {"threshold": 0.0}) is None


# ---------------------------------------------------------------------------
# pool_below_min_healthy
# ---------------------------------------------------------------------------


async def test_pool_health_triggers_below_minimum():
    pool = MagicMock()
    pool.id = uuid.uuid4()
    pool.name = "us-residential"
    db = AsyncMock()
    db.get.return_value = pool
    result = MagicMock()
    result.scalar.return_value = 2
    db.execute.return_value = result

    ctx = await _check_pool_health(db, {"pool_id": str(pool.id), "min_healthy": 5})
    assert ctx is not None
    assert ctx["pool"] == "us-residential"
    assert ctx["actual"] == 2
    assert ctx["min_healthy"] == 5


async def test_pool_health_quiet_when_enough_healthy():
    pool = MagicMock()
    pool.id = uuid.uuid4()
    pool.name = "fallback"
    db = AsyncMock()
    db.get.return_value = pool
    result = MagicMock()
    result.scalar.return_value = 9
    db.execute.return_value = result

    assert await _check_pool_health(db, {"pool_id": str(pool.id), "min_healthy": 5}) is None


async def test_pool_health_quiet_for_missing_pool():
    db = AsyncMock()
    db.get.return_value = None
    assert await _check_pool_health(db, {"pool_id": str(uuid.uuid4()), "min_healthy": 5}) is None


async def test_pool_health_quiet_without_pool_id():
    db = AsyncMock()
    assert await _check_pool_health(db, {"min_healthy": 5}) is None
    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# bandwidth_exceeded
# ---------------------------------------------------------------------------


async def test_bandwidth_triggers_over_limit():
    db = _db_returning_one((600_000_000, 500_000_000))  # 1.1 GB total
    ctx = await _check_bandwidth(db, {"limit_bytes": 1_000_000_000})
    assert ctx is not None
    assert ctx["actual_bytes"] == 1_100_000_000


async def test_bandwidth_quiet_under_limit():
    db = _db_returning_one((100, 100))
    assert await _check_bandwidth(db, {"limit_bytes": 1_000_000_000}) is None


async def test_bandwidth_quiet_without_limit():
    db = AsyncMock()
    assert await _check_bandwidth(db, {}) is None
    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# all_proxies_dead
# ---------------------------------------------------------------------------


async def test_all_dead_triggers_when_every_proxy_dead():
    db = _db_returning_all([("dead", 7)])
    ctx = await _check_all_dead(db)
    assert ctx == {"total_proxies": 7}


async def test_all_dead_quiet_with_survivors():
    db = _db_returning_all([("dead", 7), ("healthy", 1)])
    assert await _check_all_dead(db) is None


async def test_all_dead_quiet_with_no_proxies():
    db = _db_returning_all([])
    assert await _check_all_dead(db) is None


# ---------------------------------------------------------------------------
# evaluate_alerts loop: cooldown + trigger bookkeeping
# ---------------------------------------------------------------------------


def _make_rule(condition_type="all_proxies_dead", last_triggered_at=None):
    rule = MagicMock()
    rule.name = "test rule"
    rule.condition_type = condition_type
    rule.condition_config = {}
    rule.action_type = "webhook"
    rule.action_config = {"url": "https://hooks.example.com/x"}
    rule.is_enabled = True
    rule.last_triggered_at = last_triggered_at
    return rule


def _session_factory_for(db):
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=db)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


async def test_evaluate_skips_rule_in_cooldown():
    rule = _make_rule(last_triggered_at=datetime.now(UTC) - timedelta(seconds=10))
    db = AsyncMock()
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [rule]
    db.execute.return_value = rules_result

    with (
        patch("src.services.alerts.async_session_factory", _session_factory_for(db)),
        patch("src.services.alerts._evaluate_condition") as eval_mock,
    ):
        await evaluate_alerts()
    eval_mock.assert_not_called()


async def test_evaluate_fires_and_records_trigger():
    rule = _make_rule(last_triggered_at=None)
    db = AsyncMock()
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [rule]
    db.execute.return_value = rules_result

    with (
        patch("src.services.alerts.async_session_factory", _session_factory_for(db)),
        patch(
            "src.services.alerts._evaluate_condition",
            AsyncMock(return_value={"total_proxies": 3}),
        ),
        patch("src.services.alerts._fire_webhook", AsyncMock()) as hook_mock,
    ):
        await evaluate_alerts()

    assert rule.last_triggered_at is not None
    db.commit.assert_awaited()
    hook_mock.assert_awaited_once()


async def test_evaluate_survives_condition_errors():
    rule = _make_rule()
    db = AsyncMock()
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [rule]
    db.execute.return_value = rules_result

    with (
        patch("src.services.alerts.async_session_factory", _session_factory_for(db)),
        patch(
            "src.services.alerts._evaluate_condition",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch("src.services.alerts._fire_webhook", AsyncMock()) as hook_mock,
    ):
        await evaluate_alerts()  # must not raise
    hook_mock.assert_not_called()
    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# webhook delivery
# ---------------------------------------------------------------------------


async def test_webhook_posts_design_doc_payload():
    rule = _make_rule(condition_type="error_rate_above")
    sent = {}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            sent["url"] = url
            sent["json"] = json
            resp = MagicMock()
            resp.status_code = 200
            return resp

    now = datetime.now(UTC)
    with patch("src.services.alerts.httpx.AsyncClient", FakeClient):
        await _fire_webhook(rule, {"threshold": 0.2, "actual": 0.35}, now)

    assert sent["url"] == "https://hooks.example.com/x"
    assert sent["json"]["event"] == "alert.triggered"
    assert sent["json"]["alert_name"] == "test rule"
    assert sent["json"]["condition"] == {
        "type": "error_rate_above",
        "threshold": 0.2,
        "actual": 0.35,
    }
    assert sent["json"]["triggered_at"] == now.isoformat()


async def test_webhook_skips_when_url_missing():
    rule = _make_rule()
    rule.action_config = {}
    with patch("src.services.alerts.httpx.AsyncClient") as client_mock:
        await _fire_webhook(rule, {}, datetime.now(UTC))
    client_mock.assert_not_called()
