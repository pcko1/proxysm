"""Tests for the provider-health stats endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.stats import router as stats_router
from src.database import get_db

ADMIN_PASSWORD = "testpassword"

_fake_settings = MagicMock()
_fake_settings.pm_admin_password = ADMIN_PASSWORD


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(stats_router, prefix="/api/v1")
    return app


test_app = _build_test_app()


def _auth():
    return {"Authorization": f"Bearer {ADMIN_PASSWORD}"}


def _override_db(mock_db):
    """Create a dependency override for get_db that yields mock_db."""
    async def _get_db_override():
        yield mock_db
    return _get_db_override


class TestProviderHealth:
    """Test the /stats/provider-health endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_proxies(self):
        """Should return empty data list when no proxies exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_db.execute = AsyncMock(return_value=mock_result)

        test_app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                with patch("src.api.deps.settings", _fake_settings):
                    resp = await client.get("/api/v1/stats/provider-health", headers=_auth())

            assert resp.status_code == 200
            assert resp.json()["data"] == []
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_provider_breakdown(self):
        """Should return per-provider health breakdown."""
        row1 = MagicMock()
        row1.provider = "BrightData"
        row1.total = 10
        row1.healthy = 7
        row1.degraded = 2
        row1.dead = 1
        row1.unknown = 0
        row1.active = 9

        row2 = MagicMock()
        row2.provider = "IPRoyal"
        row2.total = 5
        row2.healthy = 5
        row2.degraded = 0
        row2.dead = 0
        row2.unknown = 0
        row2.active = 5

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([row1, row2]))
        mock_db.execute = AsyncMock(return_value=mock_result)

        test_app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                with patch("src.api.deps.settings", _fake_settings):
                    resp = await client.get("/api/v1/stats/provider-health", headers=_auth())

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert len(data) == 2
            assert data[0]["provider"] == "BrightData"
            assert data[0]["total"] == 10
            assert data[0]["healthy"] == 7
            assert data[0]["dead"] == 1
            assert data[0]["active"] == 9
            assert data[1]["provider"] == "IPRoyal"
            assert data[1]["total"] == 5
            assert data[1]["healthy"] == 5
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_null_provider_shows_as_unknown(self):
        """Proxies with no provider should show as 'Unknown'."""
        row = MagicMock()
        row.provider = None
        row.total = 3
        row.healthy = 1
        row.degraded = 1
        row.dead = 1
        row.unknown = 0
        row.active = 2

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([row]))
        mock_db.execute = AsyncMock(return_value=mock_result)

        test_app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                with patch("src.api.deps.settings", _fake_settings):
                    resp = await client.get("/api/v1/stats/provider-health", headers=_auth())

            assert resp.status_code == 200
            data = resp.json()["data"]
            assert len(data) == 1
            assert data[0]["provider"] == "Unknown"
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_requires_auth(self):
        """Should reject unauthenticated requests (422 = missing header, 401 = bad creds)."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_db.execute = AsyncMock(return_value=mock_result)

        test_app.dependency_overrides[get_db] = _override_db(mock_db)
        try:
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                with patch("src.api.deps.settings", _fake_settings):
                    # No auth header → 422 (missing required header)
                    resp = await client.get("/api/v1/stats/provider-health")
                    assert resp.status_code in (401, 403, 422)

                    # Wrong credentials → 401
                    resp = await client.get(
                        "/api/v1/stats/provider-health",
                        headers={"Authorization": "Bearer wrongpassword"},
                    )
                    assert resp.status_code == 401
        finally:
            test_app.dependency_overrides.clear()
