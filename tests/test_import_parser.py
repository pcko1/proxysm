"""Tests for the proxy import parser (src/services/import_parser.py)."""

import pytest

from src.services.import_parser import (
    ParsedProxy,
    _guess_protocol,
    _is_port,
    _looks_like_host,
    parse_proxy_list,
    parse_single_line,
)


# ---------------------------------------------------------------------------
# _guess_protocol
# ---------------------------------------------------------------------------

class TestGuessProtocol:
    def test_socks5_range_start(self):
        assert _guess_protocol(1080) == "socks5"

    def test_socks5_range_end(self):
        assert _guess_protocol(1089) == "socks5"

    def test_socks5_mid_range(self):
        assert _guess_protocol(1085) == "socks5"

    def test_https_443(self):
        assert _guess_protocol(443) == "https"

    def test_https_8443(self):
        assert _guess_protocol(8443) == "https"

    def test_https_8444(self):
        assert _guess_protocol(8444) == "https"

    def test_http_default(self):
        assert _guess_protocol(8080) == "http"

    def test_http_port_80(self):
        assert _guess_protocol(80) == "http"

    def test_http_port_3128(self):
        assert _guess_protocol(3128) == "http"


# ---------------------------------------------------------------------------
# _is_port
# ---------------------------------------------------------------------------

class TestIsPort:
    def test_valid_port_min(self):
        assert _is_port("1") is True

    def test_valid_port_max(self):
        assert _is_port("65535") is True

    def test_valid_port_mid(self):
        assert _is_port("8080") is True

    def test_zero_is_invalid(self):
        assert _is_port("0") is False

    def test_negative_is_invalid(self):
        assert _is_port("-1") is False

    def test_too_large(self):
        assert _is_port("65536") is False

    def test_non_numeric(self):
        assert _is_port("abc") is False

    def test_empty_string(self):
        assert _is_port("") is False


# ---------------------------------------------------------------------------
# _looks_like_host
# ---------------------------------------------------------------------------

class TestLooksLikeHost:
    def test_ipv4(self):
        assert _looks_like_host("192.168.1.1") is True

    def test_hostname(self):
        assert _looks_like_host("proxy.example.com") is True

    def test_simple_host(self):
        assert _looks_like_host("localhost") is True

    def test_port_number_not_host(self):
        assert _looks_like_host("8080") is False

    def test_empty_string(self):
        assert _looks_like_host("") is False


# ---------------------------------------------------------------------------
# parse_single_line — URL-style formats
# ---------------------------------------------------------------------------

class TestParseSingleLineURL:
    def test_url_with_auth(self):
        result = parse_single_line("http://user:pass@192.168.1.1:8080")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.protocol == "http"
        assert result.username == "user"
        assert result.password == "pass"

    def test_url_without_auth(self):
        result = parse_single_line("http://192.168.1.1:8080")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.protocol == "http"
        assert result.username is None
        assert result.password is None

    def test_https_url(self):
        result = parse_single_line("https://proxy.example.com:443")
        assert result.protocol == "https"
        assert result.host == "proxy.example.com"
        assert result.port == 443

    def test_socks5_url_with_auth(self):
        result = parse_single_line("socks5://admin:secret@10.0.0.1:1080")
        assert result.protocol == "socks5"
        assert result.username == "admin"
        assert result.password == "secret"
        assert result.port == 1080


# ---------------------------------------------------------------------------
# parse_single_line — @ separator formats
# ---------------------------------------------------------------------------

class TestParseSingleLineAtSeparator:
    def test_host_port_at_user_pass(self):
        result = parse_single_line("192.168.1.1:8080@user:pass")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"

    def test_user_pass_at_host_port(self):
        result = parse_single_line("user:pass@192.168.1.1:8080")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"


# ---------------------------------------------------------------------------
# parse_single_line — colon-separated formats
# ---------------------------------------------------------------------------

class TestParseSingleLineColonSeparated:
    def test_host_port_user_pass(self):
        result = parse_single_line("192.168.1.1:8080:user:pass")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"

    def test_user_pass_host_port(self):
        result = parse_single_line("user:pass:192.168.1.1:8080")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"

    def test_host_port_only(self):
        result = parse_single_line("192.168.1.1:8080")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username is None
        assert result.password is None


# ---------------------------------------------------------------------------
# parse_single_line — space/tab separated
# ---------------------------------------------------------------------------

class TestParseSingleLineSpaceSeparated:
    def test_space_host_port_user_pass(self):
        result = parse_single_line("192.168.1.1 8080 user pass")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"

    def test_space_host_port_only(self):
        result = parse_single_line("192.168.1.1 8080")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username is None

    def test_tab_separated(self):
        result = parse_single_line("192.168.1.1\t8080\tuser\tpass")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"


# ---------------------------------------------------------------------------
# parse_single_line — CSV format
# ---------------------------------------------------------------------------

class TestParseSingleLineCSV:
    def test_csv_host_port_user_pass(self):
        result = parse_single_line("192.168.1.1,8080,user,pass")
        assert result.host == "192.168.1.1"
        assert result.port == 8080
        assert result.username == "user"
        assert result.password == "pass"


# ---------------------------------------------------------------------------
# parse_single_line — protocol guessing
# ---------------------------------------------------------------------------

class TestProtocolGuessing:
    def test_socks5_port_guessed(self):
        result = parse_single_line("192.168.1.1:1080")
        assert result.protocol == "socks5"

    def test_https_port_guessed(self):
        result = parse_single_line("192.168.1.1:443")
        assert result.protocol == "https"

    def test_http_port_guessed(self):
        result = parse_single_line("192.168.1.1:3128")
        assert result.protocol == "http"


# ---------------------------------------------------------------------------
# parse_proxy_list — multi-line parsing
# ---------------------------------------------------------------------------

class TestParseProxyList:
    def test_multiple_proxies(self):
        text = "192.168.1.1:8080\n10.0.0.1:3128\n"
        results = parse_proxy_list(text)
        assert len(results) == 2
        assert results[0].host == "192.168.1.1"
        assert results[1].host == "10.0.0.1"

    def test_comment_lines_skipped(self):
        text = "# this is a comment\n192.168.1.1:8080\n# another comment\n"
        results = parse_proxy_list(text)
        assert len(results) == 1
        assert results[0].host == "192.168.1.1"

    def test_empty_lines_skipped(self):
        text = "\n\n192.168.1.1:8080\n\n10.0.0.1:3128\n\n"
        results = parse_proxy_list(text)
        assert len(results) == 2

    def test_empty_string(self):
        results = parse_proxy_list("")
        assert results == []

    def test_mixed_formats(self):
        text = (
            "http://user:pass@192.168.1.1:8080\n"
            "10.0.0.1:3128:admin:secret\n"
            "172.16.0.1 1080 foo bar\n"
        )
        results = parse_proxy_list(text)
        assert len(results) == 3
        assert results[0].protocol == "http"
        assert results[1].host == "10.0.0.1"
        assert results[2].port == 1080
