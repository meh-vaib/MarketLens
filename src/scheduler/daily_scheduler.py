"""Daily scheduling using APScheduler.

We use a blocking scheduler so this module can be the long-lived process
inside a Docker container.
"""

from __future__ import annotations

import signal

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_settings
from src.utils import get_logger

log = get_logger("scheduler")


def run_scheduler() -> None:
    settings = get_settings()
    sched = BlockingScheduler(timezone="UTC")

    # Lazy import to avoid heavy imports at module load
    from src.pipeline import run_pipeline

    sched.add_job(
        run_pipeline,
        trigger=CronTrigger(
            hour=settings.schedule_hour,
            minute=settings.schedule_minute,
            timezone="UTC",
        ),
        id="daily_market_intel",
        name="Daily Market Intelligence Run",
        misfire_grace_time=60 * 60,  # 1 hour grace
        max_instances=1,
        replace_existing=True,
    )

    log.info(
        f"scheduler started; daily run at {settings.schedule_hour:02d}:"
        f"{settings.schedule_minute:02d} UTC"
    )

    # Graceful shutdown
    def _shutdown(signum, frame):  # noqa: ARG001
        log.info("shutdown signal received; stopping scheduler")
        sched.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass
