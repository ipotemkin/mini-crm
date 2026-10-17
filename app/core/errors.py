"""Unified API error responses."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def make_request_id() -> str:
    return uuid.uuid4().hex[:8]


def error_body(
    code: str,
    message: str,
    request_id: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        request_id = getattr(
            request.state,
            "request_id",
            make_request_id(),
        )
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code = detail["code"]
            message = detail.get("message", str(detail))
            details = detail.get("details", [])
        else:
            code = {
                401: "unauthorized",
                403: "csrf_failed",
                404: "not_found",
                409: "conflict",
                429: "too_many_requests",
            }.get(exc.status_code, "bad_request")
            message = str(detail)
            details = []
        # HTML pages get redirect/template elsewhere; API gets JSON
        accept = request.headers.get("accept", "")
        if (
            not request.url.path.startswith("/api/")
            and "text/html" in accept
            and exc.status_code == 401
        ):
            from fastapi.responses import RedirectResponse

            return RedirectResponse(
                url="/login",
                status_code=302,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message, request_id, details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(
            request.state,
            "request_id",
            make_request_id(),
        )
        details = []
        for err in exc.errors():
            loc = err.get("loc", ())
            field = ".".join(str(x) for x in loc if x != "body")
            details.append(
                {
                    "field": field or None,
                    "message": err.get("msg", "Некорректное значение"),
                }
            )
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error",
                "Некорректные данные",
                request_id,
                details,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        request_id = getattr(
            request.state,
            "request_id",
            make_request_id(),
        )
        import logging

        logging.getLogger("app").exception(
            "Unhandled error",
            extra={"request_id": request_id},
        )
        return JSONResponse(
            status_code=500,
            content=error_body(
                "internal_error",
                "Внутренняя ошибка сервера",
                request_id,
            ),
        )


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)

    def as_http_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
