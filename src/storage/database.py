"""Thin wrapper around SQLAlchemy 2.x for our persistence needs."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from src.schemas import AnalyzedEvent, DailyReport
from src.utils import get_logger

from .models import Base, EventRecord, ReportRecord, RunRecord

log = get_logger("storage")


class Database:
    """Application-level data access object."""

    def __init__(self, url: Optional[str] = None) -> None:
        url = url or get_settings().database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, future=True, connect_args=connect_args)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        log.info(f"Database initialised at {url}")

    # ------------------------------------------------------------------ #
    # Sessions
    # ------------------------------------------------------------------ #
    @contextmanager
    def session(self) -> Session:  # type: ignore[override]
        s = self.SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def save_events(self, events: Iterable[AnalyzedEvent]) -> int:
        n = 0
        with self.session() as s:
            for ev in events:
                rec = EventRecord(
                    id=ev.item.id,
                    url=ev.item.url,
                    source=ev.item.source,
                    title=ev.item.title,
                    summary=ev.item.summary or "",
                    published_at=ev.item.published_at,
                    fetched_at=ev.item.fetched_at,
                    impact_level=ev.analysis.impact_level.value,
                    impact_direction=ev.analysis.impact_direction.value,
                    time_horizon=ev.analysis.time_horizon.value,
                    affected_sectors=json.dumps(ev.analysis.affected_sectors),
                    affected_assets=json.dumps(ev.analysis.affected_assets),
                    affected_regions=json.dumps(ev.analysis.affected_regions),
                    confidence=ev.analysis.confidence,
                    why_it_matters=ev.analysis.why_it_matters,
                    rationale=ev.analysis.rationale,
                    analysis_summary=ev.analysis.summary,
                )
                s.merge(rec)
                n += 1
        return n

    def already_seen(self, ids: Iterable[str]) -> set[str]:
        ids = list(ids)
        if not ids:
            return set()
        with self.session() as s:
            rows = s.execute(select(EventRecord.id).where(EventRecord.id.in_(ids))).all()
        return {r[0] for r in rows}

    def recent_events(self, limit: int = 50) -> List[EventRecord]:
        with self.session() as s:
            return list(
                s.execute(
                    select(EventRecord)
                    .order_by(desc(EventRecord.fetched_at))
                    .limit(limit)
                ).scalars()
            )

    # ------------------------------------------------------------------ #
    # Runs
    # ------------------------------------------------------------------ #
    def start_run(self) -> int:
        with self.session() as s:
            run = RunRecord(started_at=datetime.utcnow(), status="running")
            s.add(run)
            s.flush()
            return run.id

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        items_collected: int,
        items_analyzed: int,
        error: Optional[str] = None,
    ) -> None:
        with self.session() as s:
            run = s.get(RunRecord, run_id)
            if not run:
                return
            run.finished_at = datetime.utcnow()
            run.status = status
            run.items_collected = items_collected
            run.items_analyzed = items_analyzed
            run.error = error

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #
    def save_report(self, report: DailyReport, html: str, markdown: str) -> None:
        with self.session() as s:
            rec = ReportRecord(
                date=report.date,
                generated_at=report.generated_at,
                html=html,
                markdown=markdown,
                executive_summary=report.executive_summary,
            )
            s.merge(rec)

    def get_report(self, date: str) -> Optional[ReportRecord]:
        with self.session() as s:
            return s.get(ReportRecord, date)

    def latest_report(self) -> Optional[ReportRecord]:
        with self.session() as s:
            return s.execute(
                select(ReportRecord).order_by(desc(ReportRecord.date)).limit(1)
            ).scalar_one_or_none()


_DB: Optional[Database] = None


def get_db() -> Database:
    """Process-wide singleton."""
    global _DB
    if _DB is None:
        _DB = Database()
    return _DB
