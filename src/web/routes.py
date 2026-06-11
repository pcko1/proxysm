import hashlib
import hmac
import pathlib

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.web.auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    create_session_token,
    verify_session_token,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))


def _ctx() -> dict:
    return {
        "http_port": settings.proxy_http_port,
        "socks5_port": settings.proxy_socks5_port,
    }


def require_session(request: Request) -> None:
    """Redirect unauthenticated browsers to the login page."""
    if not verify_session_token(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
        )


def _password_ok(password: str) -> bool:
    given = hashlib.sha256(password.encode()).hexdigest()
    expected = hashlib.sha256(settings.pm_admin_password.encode()).hexdigest()
    return hmac.compare_digest(given, expected)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if verify_session_token(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, password: str = Form(...)):
    if not _password_ok(password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Wrong password. Check PM_ADMIN_PASSWORD in your .env."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout", response_class=RedirectResponse)
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/", response_class=RedirectResponse)
async def index():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "dashboard.html", _ctx())


@router.get("/stats", response_class=RedirectResponse)
async def stats_redirect():
    return RedirectResponse(url="/dashboard")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "settings.html", _ctx())


@router.get("/proxies", response_class=HTMLResponse)
async def proxies_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "proxies.html", _ctx())


@router.get("/pools", response_class=HTMLResponse)
async def pools_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "pools.html", _ctx())


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "projects.html", _ctx())


@router.get("/api-docs", response_class=HTMLResponse)
async def api_docs_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "api-docs.html", _ctx())


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, _: None = Depends(require_session)):
    return templates.TemplateResponse(request, "setup.html", _ctx())


@router.get("/providers", response_class=RedirectResponse)
async def providers_redirect():
    return RedirectResponse(url="/proxies")


def not_found_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(request, "404.html", _ctx(), status_code=404)
