"""FastAPI application entrypoint."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.api.v1 import api_router
from app.config import get_settings
from app.core.errors import make_request_id, register_exception_handlers
from app.core.logging import setup_logging
from app.core.security import get_current_user
from app.db import get_engine
from app.web import web_router
from app.web.deps import render


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = make_request_id()
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        import logging

        logging.getLogger("app.access").info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        is_settings = request.url.path.startswith("/settings")
        script_src = "'self'"
        if is_settings:
            script_src += " https://apis.google.com https://accounts.google.com"
        frame_src = "'self'"
        if is_settings:
            frame_src += " https://docs.google.com https://*.google.com"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src {script_src}; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"frame-src {frame_src}; "
            f"connect-src 'self' https://www.googleapis.com;"
        )
        return response


class AuthRedirectMiddleware(BaseHTTPMiddleware):
    PUBLIC = {"/login", "/health", "/static"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in {"/login", "/health", "/logout", "/api/v1/auth/login"}
            or path.startswith("/static")
            or path.startswith("/settings/google/oauth/")
        ):
            return await call_next(request)
        user = get_current_user(request)
        if user is None:
            accept = request.headers.get("accept", "")
            if path.startswith("/api/"):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "unauthorized",
                            "message": "Требуется авторизация",
                            "details": [],
                            "request_id": getattr(
                                request.state,
                                "request_id",
                                "",
                            ),
                        }
                    },
                )
            if "text/html" in accept or not path.startswith("/api/"):
                return RedirectResponse("/login", status_code=302)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    get_engine()
    Path("data").mkdir(exist_ok=True)
    Path(settings.backup_dir).mkdir(parents=True, exist_ok=True)
    try:
        from app.jobs.scheduler import start_scheduler, stop_scheduler

        start_scheduler()
        yield
        stop_scheduler()
    except Exception:
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Mini-CRM",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AuthRedirectMiddleware)

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(api_router)
    app.include_router(web_router)

    @app.get("/health")
    def health():
        try:
            from sqlalchemy import text

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok", "version": __version__}
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": str(exc)},
            )

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_json(request: Request):
        if get_current_user(request) is None:
            return JSONResponse(status_code=401, content={"detail": "auth"})
        return app.openapi()

    @app.get("/docs", include_in_schema=False)
    def docs(request: Request):
        if get_current_user(request) is None:
            return RedirectResponse("/login")
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Mini-CRM API",
        )

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "not_found",
                        "message": "Не найдено",
                        "details": [],
                        "request_id": getattr(
                            request.state,
                            "request_id",
                            "",
                        ),
                    }
                },
            )
        return render(request, "errors/404.html", status_code=404)

    return app


app = create_app()
