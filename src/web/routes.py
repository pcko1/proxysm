import pathlib

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))


def _ctx() -> dict:
    return {
        "admin_token": settings.pm_admin_password,
        "http_port": settings.proxy_http_port,
        "socks5_port": settings.proxy_socks5_port,
    }


@router.get("/", response_class=RedirectResponse)
async def index():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", _ctx())


@router.get("/stats", response_class=RedirectResponse)
async def stats_redirect():
    return RedirectResponse(url="/dashboard")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", _ctx())


@router.get("/proxies", response_class=HTMLResponse)
async def proxies_page(request: Request):
    return templates.TemplateResponse(request, "proxies.html", _ctx())


@router.get("/pools", response_class=HTMLResponse)
async def pools_page(request: Request):
    return templates.TemplateResponse(request, "pools.html", _ctx())


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse(request, "projects.html", _ctx())


@router.get("/api-docs", response_class=HTMLResponse)
async def api_docs_page(request: Request):
    return templates.TemplateResponse(request, "api-docs.html", _ctx())


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse(request, "setup.html", _ctx())


@router.get("/providers", response_class=RedirectResponse)
async def providers_redirect():
    return RedirectResponse(url="/proxies")


def not_found_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(request, "404.html", _ctx(), status_code=404)
