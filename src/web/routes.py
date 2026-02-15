import pathlib

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))


def _ctx(request: Request) -> dict:
    return {"request": request, "admin_token": settings.pm_admin_password}


@router.get("/", response_class=RedirectResponse)
async def index():
    return RedirectResponse(url="/stats")


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", _ctx(request))


@router.get("/dashboard", response_class=RedirectResponse)
async def dashboard_redirect():
    return RedirectResponse(url="/stats")


@router.get("/blacklist", response_class=HTMLResponse)
async def blacklist_page(request: Request):
    return templates.TemplateResponse("blacklist.html", _ctx(request))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", _ctx(request))


@router.get("/proxies", response_class=HTMLResponse)
async def proxies_page(request: Request):
    return templates.TemplateResponse("proxies.html", _ctx(request))


@router.get("/pools", response_class=HTMLResponse)
async def pools_page(request: Request):
    return templates.TemplateResponse("pools.html", _ctx(request))


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse("projects.html", _ctx(request))


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", _ctx(request))


@router.get("/providers", response_class=RedirectResponse)
async def providers_redirect():
    return RedirectResponse(url="/settings")


def not_found_handler(request: Request, exc: Exception):
    """Custom 404 handler returning styled page."""
    return templates.TemplateResponse("404.html", _ctx(request), status_code=404)
