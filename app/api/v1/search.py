"""Global search API."""

from fastapi import APIRouter

from app.api.deps import AuthUser, DbSession
from app.services import search as svc

router = APIRouter(tags=["search"])


@router.get("/search")
def search(
    db: DbSession,
    _user: AuthUser,
    q: str = "",
    limit: int = 5,
    include_archived: bool = True,
):
    return svc.global_search(db, q, limit, include_archived)
