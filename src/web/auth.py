"""Signed session cookies for the web UI.

Tokens are HMAC-signed with PM_SECRET_KEY: "<issued-unix-ts>.<signature>".
No server-side session storage; restarting the app keeps sessions valid as
long as the secret key is unchanged.
"""

import hashlib
import hmac
import time

from src.config import settings

SESSION_COOKIE = "proxysm_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600


def _sign(payload: str) -> str:
    return hmac.new(
        settings.pm_secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def create_session_token() -> str:
    issued = str(int(time.time()))
    return f"{issued}.{_sign(issued)}"


def verify_session_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    issued, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(issued)):
        return False
    try:
        return time.time() - int(issued) < SESSION_TTL_SECONDS
    except ValueError:
        return False
