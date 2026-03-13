"""Tests for the source poller sync logic (src/services/source_poller.py)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.source_poller import _sync_proxies, _poll_single_source


@pytest.fixture
def mock_source():
    """Create a mock ProxySource."""
    source = MagicMock()
    source.id = uuid.uuid4()
    source.name = "test-feed"
    source.type = "url"
    source.url = "https://example.com/proxies.txt"
    source.provider = "TestProvider"
    source.is_active = True
    source.consecutive_failures = 0
    source.last_polled_at = None
    source.last_status_code = None
    return source


@pytest.fixture
def make_parsed_proxy():
    """Factory for creating ParsedProxy-like objects."""
    def _make(host, port, protocol="http", username=None, password=None):
        from src.services.import_parser import ParsedProxy
        return ParsedProxy(host=host, port=port, protocol=protocol, username=username, password=password)
    return _make


@pytest.fixture
def make_mock_proxy():
    """Factory for creating mock Proxy objects."""
    def _make(host, port, protocol="http", source_id=None, is_active=True,
              last_health_status="unknown", username=None, password_encrypted=None):
        proxy = MagicMock()
        proxy.id = uuid.uuid4()
        proxy.host = host
        proxy.port = port
        proxy.protocol = protocol
        proxy.source_id = source_id
        proxy.is_active = is_active
        proxy.last_health_status = last_health_status
        proxy.username = username
        proxy.password_encrypted = password_encrypted
        return proxy
    return _make


class TestSyncProxies:
    """Test the _sync_proxies function."""

    @pytest.mark.asyncio
    async def test_adds_new_proxies(self, mock_source, make_parsed_proxy):
        """New proxies in feed that don't exist in DB should be added."""
        parsed = [
            make_parsed_proxy("1.2.3.4", 8080),
            make_parsed_proxy("5.6.7.8", 3128),
        ]

        mock_session = AsyncMock()
        # DB returns no existing proxies for this source
        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []
        # No cross-source duplicates
        mock_no_dup = MagicMock()
        mock_no_dup.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[mock_result_empty, mock_no_dup, mock_no_dup])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.source_poller.async_session_factory", mock_session_factory):
            await _sync_proxies(mock_source, parsed)

        # Should have called session.add twice (one for each new proxy)
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_cross_source_duplicates(self, mock_source, make_parsed_proxy):
        """Proxies that exist under a different source should be skipped."""
        parsed = [make_parsed_proxy("1.2.3.4", 8080)]

        mock_session = AsyncMock()
        # DB returns no existing proxies for this source
        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []
        # Cross-source duplicate found
        mock_dup = MagicMock()
        mock_dup.scalar_one_or_none.return_value = uuid.uuid4()

        mock_session.execute = AsyncMock(side_effect=[mock_result_empty, mock_dup])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.source_poller.async_session_factory", mock_session_factory):
            await _sync_proxies(mock_source, parsed)

        # Should not add any proxies
        assert mock_session.add.call_count == 0

    @pytest.mark.asyncio
    async def test_deactivates_disappeared_unhealthy_proxy(self, mock_source, make_mock_proxy):
        """Proxies missing from feed and unhealthy should be deactivated."""
        existing_proxy = make_mock_proxy(
            "1.2.3.4", 8080, source_id=mock_source.id,
            is_active=True, last_health_status="dead",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_proxy]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Empty feed — proxy disappeared
        with patch("src.services.source_poller.async_session_factory", mock_session_factory):
            await _sync_proxies(mock_source, [])

        assert existing_proxy.is_active is False

    @pytest.mark.asyncio
    async def test_keeps_disappeared_healthy_proxy(self, mock_source, make_mock_proxy):
        """Proxies missing from feed but healthy should NOT be deactivated."""
        existing_proxy = make_mock_proxy(
            "1.2.3.4", 8080, source_id=mock_source.id,
            is_active=True, last_health_status="healthy",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_proxy]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.source_poller.async_session_factory", mock_session_factory):
            await _sync_proxies(mock_source, [])

        # Should remain active
        assert existing_proxy.is_active is True

    @pytest.mark.asyncio
    async def test_reactivates_returning_proxy(self, mock_source, make_parsed_proxy, make_mock_proxy):
        """Proxies that reappear in feed should be reactivated."""
        existing_proxy = make_mock_proxy(
            "1.2.3.4", 8080, source_id=mock_source.id,
            is_active=False, last_health_status="dead",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_proxy]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        parsed = [make_parsed_proxy("1.2.3.4", 8080)]

        with patch("src.services.source_poller.async_session_factory", mock_session_factory):
            await _sync_proxies(mock_source, parsed)

        assert existing_proxy.is_active is True
        assert existing_proxy.last_health_status == "unknown"

    @pytest.mark.asyncio
    async def test_updates_credentials(self, mock_source, make_parsed_proxy, make_mock_proxy):
        """Proxies with changed credentials should be updated."""
        existing_proxy = make_mock_proxy(
            "1.2.3.4", 8080, source_id=mock_source.id,
            username="old_user", password_encrypted="old_pass",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_proxy]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        parsed = [make_parsed_proxy("1.2.3.4", 8080, username="new_user", password="new_pass")]

        with patch("src.services.source_poller.async_session_factory", mock_session_factory):
            await _sync_proxies(mock_source, parsed)

        assert existing_proxy.username == "new_user"
        assert existing_proxy.password_encrypted == "new_pass"


class TestPollSingleSource:
    """Test the _poll_single_source function."""

    @pytest.mark.asyncio
    async def test_increments_failures_on_http_error(self, mock_source):
        """Non-200 response should increment consecutive_failures."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = ""

        mock_session = AsyncMock()
        mock_src_obj = MagicMock()
        mock_src_obj.consecutive_failures = 0
        mock_session.get = AsyncMock(return_value=mock_src_obj)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.services.source_poller.async_session_factory", mock_session_factory),
            patch("src.services.source_poller.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _poll_single_source(mock_source)

        assert mock_src_obj.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_resets_failures_on_success(self, mock_source):
        """200 response should reset consecutive_failures to 0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "1.2.3.4:8080"

        mock_session = AsyncMock()
        mock_src_obj = MagicMock()
        mock_src_obj.consecutive_failures = 3
        mock_session.get = AsyncMock(return_value=mock_src_obj)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.services.source_poller.async_session_factory", mock_session_factory),
            patch("src.services.source_poller.httpx.AsyncClient") as mock_client_cls,
            patch("src.services.source_poller._sync_proxies", new_callable=AsyncMock) as mock_sync,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _poll_single_source(mock_source)

        assert mock_src_obj.consecutive_failures == 0
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, mock_source):
        """Connection errors should increment failures without crashing."""
        import httpx

        mock_session = AsyncMock()
        mock_src_obj = MagicMock()
        mock_src_obj.consecutive_failures = 0
        mock_session.get = AsyncMock(return_value=mock_src_obj)
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.services.source_poller.async_session_factory", mock_session_factory),
            patch("src.services.source_poller.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _poll_single_source(mock_source)

        assert mock_src_obj.consecutive_failures == 1
