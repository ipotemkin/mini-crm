"""Meta / enums endpoint."""

from fastapi import APIRouter

from app.api.deps import AuthUser
from app.core.enums import (
    CLIENT_STATUS_LABELS,
    CLIENT_TYPE_LABELS,
    DEAL_STATUS_LABELS,
    DUE_STATE_LABELS,
    ORDER_STATUS_LABELS,
    TASK_TYPE_LABELS,
)

router = APIRouter(tags=["meta"])


@router.get("/meta/enums")
def enums(_user: AuthUser) -> dict:
    def pack(labels: dict) -> list[dict]:
        return [
            {"code": k.value if hasattr(k, "value") else k, "label": v}
            for k, v in labels.items()
        ]

    return {
        "client_status": pack(CLIENT_STATUS_LABELS),
        "client_type": pack(CLIENT_TYPE_LABELS),
        "deal_status": pack(DEAL_STATUS_LABELS),
        "order_status": pack(ORDER_STATUS_LABELS),
        "task_type": pack(TASK_TYPE_LABELS),
        "due_state": pack(DUE_STATE_LABELS),
    }
