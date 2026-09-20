import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.proxies import router as proxies_router
from src.database import get_db

# ---------------------------------------------------------------------------
# Test app — only the proxies router, DB dependency overridden with a mock.
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "testpassword"

_fake_settings = MagicMock()
_fake_settings.pm_admin_password = ADMIN_PASSWORD


def _make_mock_session(captured_statements):
    """Mock AsyncSession that records executed statements and returns empty results."""
    session = AsyncMock()

    def _execute(stmt):
        captured_statements.append(stmt)
        result = MagicMock()
        result.scalar.return_value = 0
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = AsyncMock(side_effect=_execute)
    return session


def _build_test_app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(proxies_router, prefix="/api/v1")

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.mark.asyncio
@patch("src.api.deps.settings", _fake_settings)
async def test_list_proxies_search_filters_by_host_substring():
    captured = []
    app = _build_test_app(_make_mock_session(captured))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/ips",
            params={"search": "192.168"},
            headers={"Authorization": f"Bearer {ADMIN_PASSWORD}"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == []

    # Both the count query and the data query must carry the search filter.
    assert len(captured) == 2
    for stmt in captured:
        compiled = stmt.compile()
        sql = str(compiled).lower()
        assert "like" in sql, f"expected ILIKE filter in query: {sql}"
        assert "%192.168%" in compiled.params.values()


@pytest.mark.asyncio
@patch("src.api.deps.settings", _fake_settings)
async def test_check_proxy_accepts_the_checkers_three_values():
    """check_single_proxy returns (status, latency_ms, external_ip); the handler must not 500."""
    proxy = MagicMock()
    proxy.id = uuid.UUID("a0010000-0000-4000-8000-000000000001")
    proxy.host, proxy.port, proxy.protocol = "203.0.113.18", 8080, "http"
    proxy.username = None
    proxy.password_encrypted = None
    session = AsyncMock()
    session.get = AsyncMock(return_value=proxy)
    engine = MagicMock()
    engine.update_proxy_health = AsyncMock()
    engine.cache_proxy_info = AsyncMock()
    checker = AsyncMock(return_value=("healthy", 182.0, "198.51.100.9"))

    transport = ASGITransport(app=_build_test_app(session))
    with (
        patch("src.health.checker.check_single_proxy", checker),
        patch("src.api.proxies.get_redis", AsyncMock(return_value=MagicMock())),
        patch("src.api.proxies.RotationEngine", return_value=engine),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/ips/{proxy.id}/check",
                headers={"Authorization": f"Bearer {ADMIN_PASSWORD}"},
            )

    assert resp.status_code == 200
    assert resp.json() == {"id": str(proxy.id), "status": "healthy", "latency_ms": 182.0}
    assert proxy.last_health_status == "healthy"
    assert proxy.avg_latency_ms == 182.0
    engine.update_proxy_health.assert_awaited_once_with(str(proxy.id), "healthy")
