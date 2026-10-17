"""APScheduler wiring."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.jobs.backup import run_backup
from app.jobs.google_token_check import check_google_token

log = logging.getLogger("app.scheduler")
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    settings = get_settings()
    _scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    # BACKUP_CRON default "0 3 * * *"
    parts = settings.backup_cron.split()
    if len(parts) == 5:
        minute, hour, day, month, dow = parts
        _scheduler.add_job(
            run_backup,
            CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=dow,
                timezone=settings.app_timezone,
            ),
            id="backup",
            replace_existing=True,
        )
    _scheduler.add_job(
        check_google_token,
        CronTrigger(day_of_week="mon", hour=4, minute=0),
        id="google_token",
        replace_existing=True,
    )
    _scheduler.start()
    log.info("Scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
