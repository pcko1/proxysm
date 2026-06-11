"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from src.schemas.proxy import ProxyCreate, ProxyBulkImport
from src.schemas.pool import PoolCreate, PoolUpdate
from src.schemas.project import ProjectCreate


# ---------------------------------------------------------------------------
# ProxyCreate
# ---------------------------------------------------------------------------

class TestProxyCreate:
    def test_valid_minimal(self):
        p = ProxyCreate(host="192.168.1.1", port=8080, protocol="http")
        assert p.host == "192.168.1.1"
        assert p.port == 8080
        assert p.protocol == "http"
        assert p.username is None
        assert p.password is None
        assert p.provider is None

    def test_valid_full(self):
        p = ProxyCreate(
            host="proxy.example.com",
            port=443,
            protocol="https",
            provider="acme",
            username="user",
            password="pass",
        )
        assert p.provider == "acme"
        assert p.username == "user"

    def test_port_zero_valid(self):
        p = ProxyCreate(host="1.2.3.4", port=0, protocol="http")
        assert p.port == 0

    def test_port_65535_valid(self):
        p = ProxyCreate(host="1.2.3.4", port=65535, protocol="socks5")
        assert p.port == 65535

    def test_port_65536_invalid(self):
        with pytest.raises(ValidationError):
            ProxyCreate(host="1.2.3.4", port=65536, protocol="http")

    def test_port_negative_invalid(self):
        with pytest.raises(ValidationError):
            ProxyCreate(host="1.2.3.4", port=-1, protocol="http")

    def test_invalid_protocol(self):
        with pytest.raises(ValidationError):
            ProxyCreate(host="1.2.3.4", port=8080, protocol="ftp")

    def test_missing_host(self):
        with pytest.raises(ValidationError):
            ProxyCreate(port=8080, protocol="http")

    def test_missing_port(self):
        with pytest.raises(ValidationError):
            ProxyCreate(host="1.2.3.4", protocol="http")

    def test_all_protocols(self):
        for proto in ("http", "https", "socks5"):
            p = ProxyCreate(host="x", port=1, protocol=proto)
            assert p.protocol == proto


# ---------------------------------------------------------------------------
# ProxyBulkImport
# ---------------------------------------------------------------------------

class TestProxyBulkImport:
    def test_with_text(self):
        b = ProxyBulkImport(proxies="192.168.1.1:8080\n10.0.0.1:3128")
        assert b.proxies is not None
        assert b.proxy_list is None
        assert b.url is None

    def test_with_proxy_list(self):
        items = [ProxyCreate(host="1.2.3.4", port=80, protocol="http")]
        b = ProxyBulkImport(proxy_list=items)
        assert len(b.proxy_list) == 1

    def test_with_url(self):
        b = ProxyBulkImport(url="https://example.com/proxies.txt")
        assert b.url == "https://example.com/proxies.txt"

    def test_empty_valid(self):
        b = ProxyBulkImport()
        assert b.proxies is None


# ---------------------------------------------------------------------------
# PoolCreate
# ---------------------------------------------------------------------------

class TestPoolCreate:
    def test_default_strategy(self):
        p = PoolCreate(name="my-pool")
        assert p.name == "my-pool"
        assert p.rotation_strategy == "round_robin"

    def test_random_strategy(self):
        p = PoolCreate(name="pool2", rotation_strategy="random")
        assert p.rotation_strategy == "random"

    def test_weighted_random_strategy(self):
        p = PoolCreate(name="pool3", rotation_strategy="weighted_random")
        assert p.rotation_strategy == "weighted_random"

    def test_least_connections_not_exposed(self):
        # Implemented in the rotation engine, but proxy servers never maintain
        # the connections ZSET, so the strategy is intentionally not exposed.
        with pytest.raises(ValidationError):
            PoolCreate(name="pool4", rotation_strategy="least_connections")

    def test_invalid_strategy(self):
        with pytest.raises(ValidationError):
            PoolCreate(name="pool5", rotation_strategy="bogus")

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            PoolCreate()


class TestPoolUpdate:
    def test_weighted_random_strategy(self):
        p = PoolUpdate(rotation_strategy="weighted_random")
        assert p.rotation_strategy == "weighted_random"
        assert p.name is None

    def test_least_connections_not_exposed(self):
        with pytest.raises(ValidationError):
            PoolUpdate(rotation_strategy="least_connections")


# ---------------------------------------------------------------------------
# ProjectCreate
# ---------------------------------------------------------------------------

class TestProjectCreate:
    def test_valid(self):
        p = ProjectCreate(name="my-project")
        assert p.name == "my-project"

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            ProjectCreate()
