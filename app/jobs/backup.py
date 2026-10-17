"""SQLite backup via VACUUM INTO + gzip."""

from __future__ import annotations

import gzip
import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.core.timeutils import app_tz

log = logging.getLogger("app.backup")


def _db_path() -> Path:
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///"))
    raise RuntimeError("Backup supports sqlite only")


def run_backup() -> Path | None:
    settings = get_settings()
    src = _db_path()
    if not src.exists():
        log.info("No database file yet, skip backup")
        return None
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(app_tz()).strftime("%Y%m%d-%H%M%S")
    tmp = backup_dir / f"crm-{stamp}.sqlite3"
    dest = backup_dir / f"crm-{stamp}.sqlite3.gz"

    conn = sqlite3.connect(str(src))
    try:
        conn.execute(f"VACUUM INTO '{tmp}'")
    finally:
        conn.close()

    check = sqlite3.connect(str(tmp))
    try:
        row = check.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RuntimeError(f"integrity_check failed: {row}")
    finally:
        check.close()

    with open(tmp, "rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    tmp.unlink(missing_ok=True)

    _rotate(backup_dir, settings.backup_retention_days)
    log.info("Backup created: %s", dest.name)
    return dest


def _rotate(backup_dir: Path, retention_days: int) -> None:
    cutoff = datetime.now(app_tz()) - timedelta(days=retention_days)
    for path in backup_dir.glob("crm-*.sqlite3.gz"):
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=app_tz())
        if mtime < cutoff:
            path.unlink(missing_ok=True)
