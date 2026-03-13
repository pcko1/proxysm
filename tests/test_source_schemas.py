"""Tests for source-related Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.schemas.source import SourceCreate, SourceUpdate, SourceResponse
from src.schemas.proxy import ProxyBulkImport


class TestSourceCreate:
    def test_valid_url_source(self):
        s = SourceCreate(name="my-feed", type="url", url="https://example.com/proxies")
        assert s.name == "my-feed"
        assert s.type == "url"
        assert s.url == "https://example.com/proxies"

    def test_valid_manual_source(self):
        s = SourceCreate(name="manual-2026-03-13", type="manual")
        assert s.type == "manual"
        assert s.url is None

    def test_valid_file_source(self):
        s = SourceCreate(name="proxies.txt-2026-03-13", type="file")
        assert s.type == "file"

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="bad", type="ftp")

    def test_with_provider(self):
        s = SourceCreate(name="feed", type="url", provider="BrightData")
        assert s.provider == "BrightData"

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="x" * 256, type="manual")

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            SourceCreate(type="manual")

    def test_missing_type(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="test")


class TestSourceUpdate:
    def test_partial_update_name(self):
        s = SourceUpdate(name="new-name")
        data = s.model_dump(exclude_unset=True)
        assert data == {"name": "new-name"}

    def test_partial_update_is_active(self):
        s = SourceUpdate(is_active=False)
        data = s.model_dump(exclude_unset=True)
        assert data == {"is_active": False}

    def test_empty_update(self):
        s = SourceUpdate()
        data = s.model_dump(exclude_unset=True)
        assert data == {}

    def test_full_update(self):
        s = SourceUpdate(name="n", url="http://x", provider="p", is_active=True)
        data = s.model_dump(exclude_unset=True)
        assert len(data) == 4


class TestProxyBulkImportFilename:
    def test_with_filename(self):
        b = ProxyBulkImport(proxies="1.2.3.4:8080", filename="proxies.txt")
        assert b.filename == "proxies.txt"

    def test_without_filename(self):
        b = ProxyBulkImport(proxies="1.2.3.4:8080")
        assert b.filename is None
