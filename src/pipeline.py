"""End-to-end pipeline: ingest -> filter -> analyze -> report -> deliver.

This is the orchestrator that ties every component together. It is callable
both as a CLI command (``python -m src.main run-once``) and from the
scheduler / API.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from config import get_settings
from src.analysis import MarketAnalyzerAgent
from src.delivery import EmailSender
from src.filtering import RelevanceFilter
from src.ingestion import IngestionOrchestrator
from src.reporting import ReportGenerator
from src.schemas import AnalyzedEvent, NewsItem, ScoredNewsItem
from src.storage import get_db
from src.utils import get_logger, setup_logging

log = get_logger("pipeline")


@dataclass
class PipelineResult:
    status: str
    items_collected: int
    items_analyzed: int
    report_date: str | None = None
    error: str | None = None


# --------------------------------------------------------------------------- #
def run_pipeline() -> PipelineResult:
    """Synchronous entrypoint for the full daily pipeline."""
    setup_logging(level=get_settings().log_level)
    log.info("=" * 60)
    log.info("Starting AI Market Intelligence pipeline")
    log.info("=" * 60)

    db = get_db()
    run_id = db.start_run()

    try:
        # 1. INGEST
        items: list[NewsItem] = asyncio.run(_ingest())
        log.info(f"step 1/5: ingested {len(items)} items")

        # 2. FILTER
        scored = _filter(items)
        log.info(f"step 2/5: relevance-filtered to {len(scored)} items")

        # 3. ANALYZE
        analyzed = _analyze(scored)
        log.info(f"step 3/5: LLM analyzed {len(analyzed)} events")

        # 4. PERSIST
        db.save_events(analyzed)

        # 5. REPORT + DELIVER
        report_date = _report_and_deliver(analyzed, total_collected=len(items))
        log.info(f"step 5/5: report delivered for {report_date}")

        db.finish_run(
            run_id,
            status="success",
            items_collected=len(items),
            items_analyzed=len(analyzed),
        )
        return PipelineResult(
            status="success",
            items_collected=len(items),
            items_analyzed=len(analyzed),
            report_date=report_date,
        )

    except Exception as e:  # noqa: BLE001
        log.exception(f"pipeline failed: {e}")
        db.finish_run(run_id, status="failed", items_collected=0, items_analyzed=0, error=str(e))
        return PipelineResult(status="failed", items_collected=0, items_analyzed=0, error=str(e))


# --------------------------------------------------------------------------- #
async def _ingest() -> list[NewsItem]:
    orch = IngestionOrchestrator()
    return await orch.collect_all()


def _filter(items: list[NewsItem]) -> list[ScoredNewsItem]:
    s = get_settings()
    f = RelevanceFilter(threshold=s.relevance_threshold)
    scored = f.filter(items)
    log.info(
        f"  relevance filter kept {len(scored)}/{len(items)} items (threshold={s.relevance_threshold})"
    )
    # Drop items already analyzed in a previous run (deduplicate across days)
    seen = get_db().already_seen([s.item.id for s in scored])
    fresh = [s_ for s_ in scored if s_.item.id not in seen]
    if seen:
        log.info(f"  skipped {len(seen)} already-analyzed items, {len(fresh)} fresh")
    # Cap LLM cost
    capped = fresh[: s.max_items_to_analyze]
    if len(fresh) > s.max_items_to_analyze:
        log.info(f"  capped to {s.max_items_to_analyze} items (MAX_ITEMS_TO_ANALYZE)")
    return capped


def _analyze(scored: list[ScoredNewsItem]) -> list[AnalyzedEvent]:
    agent = MarketAnalyzerAgent()
    return agent.analyze_many(scored)


def _report_and_deliver(events: list[AnalyzedEvent], total_collected: int) -> str:
    generator = ReportGenerator()
    sources_used = sorted({e.item.source for e in events})
    report = generator.build(
        events=events,
        total_items_collected=total_collected,
        sources_used=sources_used,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    artefacts = generator.render(report)

    # Persist the full HTML/Markdown (these go to the hosted site)
    html = artefacts["html"].read_text(encoding="utf-8")
    markdown = artefacts["markdown"].read_text(encoding="utf-8")
    get_db().save_report(report, html=html, markdown=markdown)

    # Email delivery (best-effort): send a condensed top-N digest with a link
    # to the full report on the hosted site, rather than the entire report.
    settings = get_settings()
    sender = EmailSender()
    if sender.is_configured():
        report_url = settings.report_url(report.date)
        digest_html, digest_text = generator.render_email_digest(
            report, top_n=settings.email_top_n, report_url=report_url
        )
        sender.send_report(
            subject=f"Market Intelligence — {report.date}",
            html=digest_html,
            markdown_text=digest_text,
        )

    return report.date
