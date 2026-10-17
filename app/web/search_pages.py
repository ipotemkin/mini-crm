"""Search results page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import search as svc
from app.web.deps import render, require_web_user

router = APIRouter(tags=["web-search"])


@router.get("/search")
def search_page(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    result = svc.global_search(db, q, limit=50, include_archived=True)
    return render(
        request,
        "search/results.html",
        {"q": q, "result": result},
    )
