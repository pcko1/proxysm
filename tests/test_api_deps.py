import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.deps import admin_auth, get_project_by_api_key


# ---------------------------------------------------------------------------
# admin_auth tests
# ---------------------------------------------------------------------------

FAKE_PASSWORD = "testpassword"


def _make_settings(**overrides):
    mock = MagicMock()
    mock.pm_admin_password = overrides.get("pm_admin_password", FAKE_PASSWORD)
    return mock


@pytest.mark.asyncio
@patch("src.api.deps.settings", _make_settings())
async def test_admin_auth_valid_token():
    await admin_auth(authorization=f"Bearer {FAKE_PASSWORD}")


@pytest.mark.asyncio
@patch("src.api.deps.settings", _make_settings())
async def test_admin_auth_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        await admin_auth(authorization="Bearer wrongpassword")
    assert exc_info.value.status_code == 401
    assert "Invalid admin credentials" in exc_info.value.detail


@pytest.mark.asyncio
@patch("src.api.deps.settings", _make_settings())
async def test_admin_auth_missing_bearer_prefix():
    with pytest.raises(HTTPException) as exc_info:
        await admin_auth(authorization="Token something")
    assert exc_info.value.status_code == 401
    assert "Invalid authorization header format" in exc_info.value.detail


@pytest.mark.asyncio
@patch("src.api.deps.settings", _make_settings())
async def test_admin_auth_empty_bearer_token():
    """Bearer prefix present but the token portion is empty."""
    with pytest.raises(HTTPException) as exc_info:
        await admin_auth(authorization="Bearer ")
    assert exc_info.value.status_code == 401
    assert "Invalid admin credentials" in exc_info.value.detail


@pytest.mark.asyncio
@patch("src.api.deps.settings", _make_settings())
async def test_admin_auth_no_space_after_bearer():
    with pytest.raises(HTTPException) as exc_info:
        await admin_auth(authorization="Bearertoken")
    assert exc_info.value.status_code == 401
    assert "Invalid authorization header format" in exc_info.value.detail


@pytest.mark.asyncio
@patch("src.api.deps.settings", _make_settings())
async def test_admin_auth_hash_comparison():
    """Verify the hash-based comparison works correctly (same plaintext)."""
    password = FAKE_PASSWORD
    token_hash = hashlib.sha256(password.encode()).hexdigest()
    password_hash = hashlib.sha256(FAKE_PASSWORD.encode()).hexdigest()
    assert token_hash == password_hash
    # Should not raise
    await admin_auth(authorization=f"Bearer {password}")


# ---------------------------------------------------------------------------
# get_project_by_api_key tests
# ---------------------------------------------------------------------------

def _mock_db_session(return_value):
    """Create an AsyncMock db session whose execute().scalar_one_or_none() returns *return_value*."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = return_value
    db.execute.return_value = result_mock
    return db


@pytest.mark.asyncio
async def test_get_project_by_api_key_missing_header():
    db = _mock_db_session(None)
    with pytest.raises(HTTPException) as exc_info:
        await get_project_by_api_key(x_api_key=None, db=db)
    assert exc_info.value.status_code == 401
    assert "X-API-Key header required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_project_by_api_key_valid_key():
    fake_project = MagicMock()
    fake_project.name = "test-project"
    db = _mock_db_session(fake_project)

    project = await get_project_by_api_key(x_api_key="valid-key-123", db=db)

    assert project is fake_project
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_by_api_key_invalid_key():
    db = _mock_db_session(None)
    with pytest.raises(HTTPException) as exc_info:
        await get_project_by_api_key(x_api_key="bad-key", db=db)
    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_project_by_api_key_empty_string():
    """An empty string should be treated the same as a missing header."""
    db = _mock_db_session(None)
    with pytest.raises(HTTPException) as exc_info:
        await get_project_by_api_key(x_api_key="", db=db)
    assert exc_info.value.status_code == 401
