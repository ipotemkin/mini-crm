"""Weekly Google refresh-token health check."""

from __future__ import annotations

import logging

from app import db as dbmod
from app.export import oauth, token_store

log = logging.getLogger("app.google")


def check_google_token() -> None:
    dbmod.get_engine()
    assert dbmod.SessionLocal is not None
    db = dbmod.SessionLocal()
    try:
        row = token_store.get_credentials(db)
        if row is None or not row.refresh_token_encrypted:
            return
        oauth.get_credentials_obj(db)
        log.info("Google token refresh OK")
    except Exception as exc:
        log.warning("Google token check failed: %s", exc)
        token_store.mark_reauth_required(db, str(exc))
    finally:
        db.close()
