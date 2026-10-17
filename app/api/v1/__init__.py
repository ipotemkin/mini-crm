"""API v1 routers."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    clients,
    deals,
    exports,
    meta,
    orders,
    search,
    tasks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(meta.router)
api_router.include_router(clients.router)
api_router.include_router(deals.router)
api_router.include_router(orders.router)
api_router.include_router(tasks.router)
api_router.include_router(search.router)
api_router.include_router(exports.router)
