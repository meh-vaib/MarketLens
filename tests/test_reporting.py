from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.reporting import ReportGenerator
from src.schemas import (
    AnalyzedEvent,
    ImpactDirection,
    ImpactLevel,
    MarketAnalysis,
    NewsItem,
    TimeHorizon,
)


def _make_event(level: ImpactLevel = ImpactLevel.HIGH) -> AnalyzedEvent:
    item = NewsItem(
        id="x",
        source="Reuters",
        title="Fed cuts rates",
        url="https://example.com",
        summary="Rate cut",
        published_at=datetime.utcnow(),
    )
    analysis = MarketAnalysis(
        headline="Fed cuts 25bps",
        summary="Rate cut summary.",
        why_it_matters="Bullish for equities.",
        impact_level=level,
        impact_direction=ImpactDirection.BULLISH,
        time_horizon=TimeHorizon.SHORT_TERM,
        affected_sectors=["Financials"],
        affected_assets=["SPX"],
        affected_regions=["US"],
        confidence=0.85,
        rationale="Lower discount rate.",
    )
    return AnalyzedEvent(item=item, analysis=analysis)


def test_report_renders_html_and_markdown(tmp_path: Path):
    gen = ReportGenerator(output_dir=tmp_path)
    with patch.object(gen, "_executive_summary", return_value="Today is bullish."):
        report = gen.build(
            events=[_make_event()],
            total_items_collected=10,
            sources_used=["Reuters"],
            date="2026-01-01",
        )
    artefacts = gen.render(report)
    html = artefacts["html"].read_text(encoding="utf-8")
    md = artefacts["markdown"].read_text(encoding="utf-8")
    assert "Daily Market Intelligence" in html
    assert "Fed cuts 25bps" in html
    assert "HIGH" in html
    assert "Daily Market Intelligence" in md
