from datetime import datetime
from unittest.mock import MagicMock

from src.analysis.market_analyzer import MarketAnalyzerAgent
from src.schemas import ImpactDirection, ImpactLevel, NewsItem, ScoredNewsItem, TimeHorizon


def _make_item() -> NewsItem:
    return NewsItem(
        id="x",
        source="test",
        title="Fed cuts rates by 25bps",
        url="https://example.com",
        summary="Surprise easing as inflation eases.",
        published_at=datetime.utcnow(),
    )


def test_analyze_one_parses_llm_json():
    fake_client = MagicMock()
    fake_client.complete_json.return_value = {
        "headline": "Fed cuts 25bps",
        "summary": "The Fed cut rates by 25 basis points.",
        "why_it_matters": "Easier financial conditions support equities.",
        "impact_level": "HIGH",
        "impact_direction": "BULLISH",
        "time_horizon": "SHORT_TERM",
        "affected_sectors": ["Financials", "Technology"],
        "affected_assets": ["SPX", "USD"],
        "affected_regions": ["US"],
        "confidence": 0.8,
        "rationale": "Lower rates -> risk on.",
    }
    agent = MarketAnalyzerAgent(client=fake_client)
    ev = agent.analyze_one(_make_item())
    assert ev is not None
    assert ev.analysis.impact_level == ImpactLevel.HIGH
    assert ev.analysis.impact_direction == ImpactDirection.BULLISH
    assert ev.analysis.time_horizon == TimeHorizon.SHORT_TERM
    assert ev.analysis.confidence == 0.8


def test_analyze_one_returns_none_when_llm_fails():
    fake_client = MagicMock()
    fake_client.complete_json.return_value = None
    agent = MarketAnalyzerAgent(client=fake_client)
    assert agent.analyze_one(_make_item()) is None


def test_analyze_many_skips_irrelevant_events():
    fake_client = MagicMock()
    fake_client.complete_json.return_value = {
        "headline": "x",
        "summary": "x",
        "why_it_matters": "",
        "impact_level": "NONE",
        "impact_direction": "NEUTRAL",
        "time_horizon": "SHORT_TERM",
        "affected_sectors": [],
        "affected_assets": [],
        "affected_regions": [],
        "confidence": 0.1,
        "rationale": "",
    }
    agent = MarketAnalyzerAgent(client=fake_client, max_workers=1)
    out = agent.analyze_many([ScoredNewsItem(item=_make_item(), relevance_score=1.0)])
    assert out == []
