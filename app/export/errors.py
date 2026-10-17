"""Map Google API errors to application codes."""

from __future__ import annotations

from app.core.errors import AppError


REASON_MAP = {
    "notFound": ("google_folder_not_found", 502, "Папка не найдена"),
    "insufficientFilePermissions": (
        "google_folder_permission_denied",
        502,
        "Нет прав на добавление файлов в папку",
    ),
    "storageQuotaExceeded": (
        "google_storage_quota_exceeded",
        502,
        "Хранилище Google Drive заполнено",
    ),
    "numChildrenInNonRootLimitExceeded": (
        "google_folder_limit_exceeded",
        502,
        "В папке достигнут лимит элементов",
    ),
    "activeItemCreationLimitExceeded": (
        "google_folder_limit_exceeded",
        502,
        "Достигнут лимит числа файлов аккаунта Google",
    ),
    "domainPolicy": (
        "google_domain_policy",
        502,
        "Администратор Workspace запретил доступ",
    ),
    "admin_policy_enforced": (
        "google_domain_policy",
        502,
        "Администратор Workspace запретил доступ",
    ),
    "rateLimitExceeded": (
        "google_unavailable",
        502,
        "Google временно недоступен",
    ),
    "userRateLimitExceeded": (
        "google_unavailable",
        502,
        "Google временно недоступен",
    ),
    "dailyLimitExceeded": (
        "google_quota_exceeded",
        502,
        "Исчерпана суточная квота Google API",
    ),
    "authError": (
        "google_reauth_required",
        502,
        "Доступ к Google-аккаунту утрачен",
    ),
}


def raise_google_error(exc: Exception) -> None:
    status = getattr(exc, "status_code", None) or getattr(
        exc, "resp", None
    )
    reason = None
    if hasattr(exc, "error_details"):
        details = exc.error_details
        if details and isinstance(details, list):
            reason = details[0].get("reason")
    content = getattr(exc, "content", b"") or b""
    text = content.decode("utf-8", errors="ignore") if content else str(exc)
    if "invalid_grant" in text:
        raise AppError(
            "google_reauth_required",
            "Доступ к Google-аккаунту утрачен. "
            "Переподключите Google в настройках",
            status_code=502,
        )
    http_status = getattr(status, "status", None) if status else None
    if reason and reason in REASON_MAP:
        code, code_status, message = REASON_MAP[reason]
        raise AppError(code, message, status_code=code_status)
    if http_status in {429, 500, 502, 503}:
        raise AppError(
            "google_unavailable",
            "Google временно недоступен, повторите позже",
            status_code=502,
        )
    raise AppError(
        "google_unavailable",
        f"Ошибка Google API: {exc}",
        status_code=502,
    )
