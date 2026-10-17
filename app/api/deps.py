"""API dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_user, verify_csrf
from app.db import get_db

DbSession = Annotated[Session, Depends(get_db)]
AuthUser = CurrentUser


def csrf_protect(request: Request) -> None:
    verify_csrf(request)


Csrf = Annotated[None, Depends(csrf_protect)]
Auth = Annotated[object, Depends(require_user)]
