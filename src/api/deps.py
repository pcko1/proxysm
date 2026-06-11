import hashlib

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models.project import Project
from src.web.auth import SESSION_COOKIE, verify_session_token


async def admin_auth(request: Request, authorization: str | None = Header(None)) -> None:
    """Authenticate as admin via Bearer token or web session cookie."""
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
            )
        token = authorization[7:]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        password_hash = hashlib.sha256(settings.pm_admin_password.encode()).hexdigest()
        if token_hash != password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials",
            )
        return
    if verify_session_token(request.cookies.get(SESSION_COOKIE)):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def get_project_by_api_key(
    x_api_key: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Validate API key and return project."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header required",
        )
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    stmt = select(Project).where(Project.api_key_hash == key_hash)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return project
