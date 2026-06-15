"""FastAPI dashboard + REST API."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from config import get_settings
from src.storage import get_db
from src.utils import get_logger

log = get_logger("api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Market Intelligence API",
        description="Daily market intelligence reports powered by LLM analysis.",
        version="1.0.0",
    )
    settings = get_settings()
    db = get_db()

    # ---------------------------------------------------------------- #
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ---------------------------------------------------------------- #
    @app.get("/", response_class=HTMLResponse)
    def root():
        latest = db.latest_report()
        if not latest:
            return HTMLResponse(
                "<h1>AI Market Intelligence</h1><p>No reports generated yet. "
                "Run <code>python -m src.main run-once</code> to create one.</p>"
            )
        return HTMLResponse(latest.html or "<p>(empty)</p>")

    # ---------------------------------------------------------------- #
    @app.get("/report/latest", response_class=HTMLResponse)
    def latest_report():
        rec = db.latest_report()
        if not rec:
            raise HTTPException(404, "no reports yet")
        return HTMLResponse(rec.html or "")

    # ---------------------------------------------------------------- #
    @app.get("/report/{date}", response_class=HTMLResponse)
    def report_by_date(date: str):
        rec = db.get_report(date)
        if not rec:
            raise HTTPException(404, f"no report for {date}")
        return HTMLResponse(rec.html or "")

    # ---------------------------------------------------------------- #
    @app.get("/report/{date}.md", response_class=PlainTextResponse)
    def report_markdown(date: str):
        rec = db.get_report(date)
        if not rec:
            raise HTTPException(404, f"no report for {date}")
        return PlainTextResponse(rec.markdown or "")

    # ---------------------------------------------------------------- #
    @app.get("/events")
    def events(limit: int = Query(50, ge=1, le=500)):
        rows = db.recent_events(limit=limit)
        return JSONResponse(
            [
                {
                    "id": r.id,
                    "title": r.title,
                    "url": r.url,
                    "source": r.source,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
                    "impact_level": r.impact_level,
                    "impact_direction": r.impact_direction,
                    "time_horizon": r.time_horizon,
                    "affected_sectors": _safe_json(r.affected_sectors),
                    "affected_assets": _safe_json(r.affected_assets),
                    "affected_regions": _safe_json(r.affected_regions),
                    "confidence": r.confidence,
                    "why_it_matters": r.why_it_matters,
                    "summary": r.analysis_summary,
                }
                for r in rows
            ]
        )

    # ---------------------------------------------------------------- #
    @app.post("/run")
    def trigger_run(x_api_key: Optional[str] = Header(None)):
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(401, "invalid API key")
        # Imported lazily to avoid a circular import at module load time
        from src.pipeline import run_pipeline

        result = run_pipeline()
        return {
            "status": result.status,
            "items_collected": result.items_collected,
            "items_analyzed": result.items_analyzed,
            "report_date": result.report_date,
        }

    return app


def _safe_json(s: Optional[str]):
    if not s:
        return []
    try:
        return json.loads(s)
    except Exception:
        return []


# Convenience instance for ``uvicorn src.delivery.api_server:app``
app = create_app()
