"""HTML / HTMX web routers."""

from fastapi import APIRouter

from app.web import (
    auth_pages,
    clients_pages,
    deals_pages,
    google_oauth,
    home,
    orders_pages,
    search_pages,
    settings_pages,
    tasks_pages,
)

web_router = APIRouter()
web_router.include_router(auth_pages.router)
web_router.include_router(home.router)
web_router.include_router(clients_pages.router)
web_router.include_router(deals_pages.router)
web_router.include_router(orders_pages.router)
web_router.include_router(tasks_pages.router)
web_router.include_router(search_pages.router)
web_router.include_router(settings_pages.router)
web_router.include_router(google_oauth.router)
