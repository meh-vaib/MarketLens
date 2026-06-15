"""Sandbox-friendly demo run.

Why this exists: the sandbox we run in cannot reach the user's local Ollama
nor the public RSS feeds. To still produce a faithful sample run we:
  1. Feed a hand-curated list of realistic recent-style news items.
  2. Stub the LLM client with deterministic Mistral-like JSON responses.
  3. Run the EXACT same analysis + reporting + persistence pipeline.

The output (HTML/MD report, SQLite DB) is identical in structure to a real
production run.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure config picks up our intent before any settings cache is created
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_MODEL"] = "mistral"
os.environ["EMAIL_ENABLED"] = "false"

from src.analysis import market_analyzer  # noqa: E402
from src.filtering import RelevanceFilter  # noqa: E402
from src.reporting import ReportGenerator  # noqa: E402
from src.classification import EventClassifier  # noqa: E402
from src.schemas import (  # noqa: E402
    AnalyzedEvent,
    ImpactDirection,
    ImpactLevel,
    MarketAnalysis,
    NewsItem,
    TimeHorizon,
)
from src.storage import get_db  # noqa: E402
from src.utils import content_hash, get_logger, setup_logging  # noqa: E402

setup_logging(level="INFO")
log = get_logger("demo")


# --------------------------------------------------------------------------- #
# Synthetic but realistic news batch (would normally come from RSS).
# --------------------------------------------------------------------------- #
SYNTHETIC_NEWS = [
    {
        "source": "Reuters Markets",
        "title": "Federal Reserve holds rates steady, signals two cuts in 2026",
        "summary": (
            "The FOMC kept the federal funds rate at 4.25-4.50% but the dot plot "
            "now shows two 25bp cuts this year as inflation eases toward target. "
            "Powell said the committee remains data-dependent."
        ),
        "category": "central_bank",
    },
    {
        "source": "Bloomberg",
        "title": "OPEC+ surprises markets with 500,000 bpd output cut extension",
        "summary": (
            "OPEC+ extended voluntary production cuts through Q3 2026, citing "
            "soft demand from China. Brent jumped 3.2% to $87/bbl on the news."
        ),
        "category": "commodities",
    },
    {
        "source": "Financial Times",
        "title": "US CPI prints at 2.4% YoY, below 2.6% consensus",
        "summary": (
            "Headline inflation cooled more than expected in March. Core CPI at "
            "2.9%. Treasury yields fell 8bps across the curve. Dollar index lost 0.6%."
        ),
        "category": "macro",
    },
    {
        "source": "CNBC",
        "title": "Nvidia tops $4 trillion market cap on AI demand surge",
        "summary": (
            "Shares rallied 4.1% after the company reaffirmed FY guidance and "
            "announced two new sovereign-AI deals. Semiconductor index up 2.3%."
        ),
        "category": "equities",
    },
    {
        "source": "Reuters World",
        "title": "Middle East tensions escalate after Red Sea shipping incident",
        "summary": (
            "Three commercial vessels reported damage; major shippers re-routing "
            "around Cape of Good Hope. Insurance premia spiking. Brent +1.8% in "
            "after-hours trading."
        ),
        "category": "geopolitics",
    },
    {
        "source": "ECB Press",
        "title": "ECB cuts deposit rate by 25bps to 2.50%, signals pause",
        "summary": (
            "Lagarde struck a cautious tone, saying further easing depends on "
            "wage data. EUR/USD fell 0.4% to 1.0820. European bank stocks slipped."
        ),
        "category": "central_bank",
    },
    {
        "source": "Yahoo Finance",
        "title": "Kardashian announces new fashion line in Milan",
        "summary": "Celebrity endorsement deal sparks social media buzz.",
        "category": "noise",  # should be filtered out
    },
    {
        "source": "Investing.com",
        "title": "China announces $200B fiscal stimulus targeting property sector",
        "summary": (
            "Beijing unveiled measures to recapitalise distressed developers and "
            "support household consumption. Hang Seng rallied 2.8%; iron ore +4%."
        ),
        "category": "macro",
    },
    {
        "source": "MarketWatch",
        "title": "Apple unveils on-device AI chip, shares up 2.5% pre-market",
        "summary": (
            "The new M5 chip targets edge AI inference. Analysts raised price "
            "targets citing services revenue acceleration."
        ),
        "category": "equities",
    },
    {
        "source": "BBC World",
        "title": "Local football team wins championship after dramatic final",
        "summary": "Sports recap of yesterday's match.",
        "category": "noise",  # should be filtered out
    },
    {
        "source": "Bank of Japan",
        "title": "BoJ holds rates, hints at gradual normalisation",
        "summary": (
            "Ueda emphasised sustainable wage-price spiral as precondition for "
            "further hikes. JPY weakened past 152 against the dollar."
        ),
        "category": "central_bank",
    },
    {
        "source": "Reuters Business",
        "title": "Tariff deadline looms; US-EU trade talks stall on auto duties",
        "summary": (
            "European auto stocks dropped 2.4% on reports negotiations missed "
            "key milestones. Treasury Secretary urged compromise within 10 days."
        ),
        "category": "geopolitics",
    },
]


# --------------------------------------------------------------------------- #
# Mistral-style stub LLM responses (deterministic, no network call).
# --------------------------------------------------------------------------- #
STUB_ANALYSES: dict[str, dict] = {
    "fed-hold": dict(
        headline="Fed holds; dot plot signals two 2026 cuts",
        summary=(
            "The FOMC left rates unchanged at 4.25-4.50% but the updated dot plot "
            "now projects two 25bp cuts this year, validating market expectations."
        ),
        why_it_matters=(
            "A more dovish Fed lowers the discount rate for risk assets and "
            "supports a weaker dollar trajectory."
        ),
        impact_level="HIGH",
        impact_direction="BULLISH",
        time_horizon="MEDIUM_TERM",
        affected_sectors=["Financials", "Technology", "Real Estate"],
        affected_assets=["SPX", "USD", "US10Y", "Gold"],
        affected_regions=["US", "Global"],
        confidence=0.82,
        rationale=(
            "Lower forward rates -> lower discount factor -> higher equity "
            "valuations; USD typically softens on dovish surprises."
        ),
    ),
    "opec": dict(
        headline="OPEC+ extends production cuts through Q3",
        summary=(
            "The cartel surprised the market by extending voluntary cuts; Brent "
            "rallied above $87 immediately."
        ),
        why_it_matters=(
            "Tighter supply at a time of subdued demand keeps a floor under crude "
            "prices and pressures inflation expectations higher."
        ),
        impact_level="HIGH",
        impact_direction="MIXED",
        time_horizon="SHORT_TERM",
        affected_sectors=["Energy", "Industrials", "Consumer Discretionary"],
        affected_assets=["Brent", "WTI", "USD", "XLE"],
        affected_regions=["Global", "Middle East"],
        confidence=0.78,
        rationale=(
            "Bullish for energy equities, bearish for transports and consumer "
            "discretionary; modestly hawkish implication for central banks."
        ),
    ),
    "cpi": dict(
        headline="US CPI cools to 2.4%, below consensus",
        summary=(
            "Headline inflation undershot expectations; Treasury yields fell "
            "across the curve and the dollar weakened."
        ),
        why_it_matters=(
            "Confirms the disinflation trajectory that underpins the Fed's "
            "easing bias - directly bullish for duration and risk assets."
        ),
        impact_level="HIGH",
        impact_direction="BULLISH",
        time_horizon="SHORT_TERM",
        affected_sectors=["Technology", "Real Estate", "Utilities"],
        affected_assets=["US10Y", "SPX", "NDX", "USD", "Gold"],
        affected_regions=["US"],
        confidence=0.85,
        rationale="Soft inflation surprise -> rates rally -> growth-stock outperformance.",
    ),
    "nvidia": dict(
        headline="Nvidia crosses $4T market cap on AI demand",
        summary=(
            "Sovereign-AI deals and reaffirmed guidance drove a 4% rally and "
            "lifted the broader semiconductor complex."
        ),
        why_it_matters=(
            "Reinforces the AI capex super-cycle thesis and underwrites the "
            "tech-led leadership in US equities."
        ),
        impact_level="MEDIUM",
        impact_direction="BULLISH",
        time_horizon="MEDIUM_TERM",
        affected_sectors=["Technology", "Communication Services"],
        affected_assets=["NDX", "SPX", "SOX"],
        affected_regions=["US", "Global"],
        confidence=0.7,
        rationale="Single-name strength with broad sector spillover via SOX/NDX weights.",
    ),
    "redsea": dict(
        headline="Red Sea shipping incident escalates supply-chain risk",
        summary=(
            "Damage to commercial vessels triggers re-routing and insurance "
            "premium spikes; oil rallied in after-hours."
        ),
        why_it_matters=(
            "Logistics disruption raises imported-goods inflation risk and adds "
            "a geopolitical risk premium to crude."
        ),
        impact_level="HIGH",
        impact_direction="BEARISH",
        time_horizon="SHORT_TERM",
        affected_sectors=["Energy", "Industrials", "Consumer Discretionary"],
        affected_assets=["Brent", "WTI", "Gold", "USD", "VIX"],
        affected_regions=["Middle East", "Global"],
        confidence=0.72,
        rationale="Geopolitical shock -> safe-haven bid + energy spike + risk-off equities.",
    ),
    "ecb": dict(
        headline="ECB cuts 25bps; Lagarde signals pause",
        summary=(
            "Deposit rate down to 2.50%; Lagarde tied further easing to wage data."
        ),
        why_it_matters=(
            "Telegraphs that the easing cycle in Europe is shallower than markets "
            "had priced; supports EUR over the medium term."
        ),
        impact_level="MEDIUM",
        impact_direction="MIXED",
        time_horizon="MEDIUM_TERM",
        affected_sectors=["Financials"],
        affected_assets=["EUR", "DAX", "EU10Y"],
        affected_regions=["EU"],
        confidence=0.68,
        rationale="Dovish action paired with hawkish guidance - net mixed.",
    ),
    "china": dict(
        headline="China unveils $200B property-sector stimulus",
        summary=(
            "Beijing announced recapitalisation measures for distressed "
            "developers; Hang Seng and industrial commodities rallied."
        ),
        why_it_matters=(
            "Reduces tail-risk in Chinese real estate and supports demand for "
            "industrial commodities globally."
        ),
        impact_level="HIGH",
        impact_direction="BULLISH",
        time_horizon="MEDIUM_TERM",
        affected_sectors=["Materials", "Industrials", "Real Estate", "Financials"],
        affected_assets=["Iron Ore", "Copper", "HSI", "AUD"],
        affected_regions=["China", "Asia", "Global"],
        confidence=0.74,
        rationale="Fiscal backstop + commodity demand impulse - reflationary for EM.",
    ),
    "apple": dict(
        headline="Apple announces M5 on-device AI chip",
        summary=(
            "New chip targets edge AI; analysts raised price targets on "
            "services revenue acceleration."
        ),
        why_it_matters=(
            "Strengthens Apple's AI narrative and is supportive for the broader "
            "consumer-tech complex."
        ),
        impact_level="MEDIUM",
        impact_direction="BULLISH",
        time_horizon="MEDIUM_TERM",
        affected_sectors=["Technology", "Consumer Discretionary"],
        affected_assets=["NDX", "SPX"],
        affected_regions=["US"],
        confidence=0.65,
        rationale="Single-name catalyst with positive tape implications.",
    ),
    "boj": dict(
        headline="BoJ holds, hints at gradual normalisation",
        summary=(
            "Ueda kept policy unchanged but signaled openness to more hikes "
            "if wage-price dynamics persist."
        ),
        why_it_matters=(
            "JPY weakness past 152 raises the probability of FX intervention; "
            "carry-trade unwind risk creeping back in."
        ),
        impact_level="MEDIUM",
        impact_direction="MIXED",
        time_horizon="MEDIUM_TERM",
        affected_sectors=["Financials"],
        affected_assets=["JPY", "Nikkei", "JGB"],
        affected_regions=["Japan"],
        confidence=0.6,
        rationale="Dovish status quo + hawkish forward guidance - net mixed.",
    ),
    "tariff": dict(
        headline="US-EU trade talks stall on auto duties",
        summary=(
            "European autos sold off on missed negotiation milestones; tariff "
            "deadline approaching."
        ),
        why_it_matters=(
            "A failure to compromise would re-introduce a meaningful trade-war "
            "risk premium into European equities and EUR."
        ),
        impact_level="MEDIUM",
        impact_direction="BEARISH",
        time_horizon="SHORT_TERM",
        affected_sectors=["Consumer Discretionary", "Industrials"],
        affected_assets=["DAX", "EUR", "EUR/USD"],
        affected_regions=["EU", "US"],
        confidence=0.66,
        rationale="Tariff overhang typically compresses European cyclicals.",
    ),
}


def stub_for(item: NewsItem) -> dict | None:
    """Map a synthetic news item to its stubbed Mistral analysis dict."""
    t = item.title.lower()
    if "federal reserve" in t or "fomc" in t:
        return STUB_ANALYSES["fed-hold"]
    if "opec" in t:
        return STUB_ANALYSES["opec"]
    if "cpi" in t:
        return STUB_ANALYSES["cpi"]
    if "nvidia" in t:
        return STUB_ANALYSES["nvidia"]
    if "red sea" in t:
        return STUB_ANALYSES["redsea"]
    if "ecb" in t:
        return STUB_ANALYSES["ecb"]
    if "china" in t and "stimulus" in t:
        return STUB_ANALYSES["china"]
    if "apple" in t:
        return STUB_ANALYSES["apple"]
    if "boj" in t or "bank of japan" in t:
        return STUB_ANALYSES["boj"]
    if "tariff" in t or "trade talks" in t:
        return STUB_ANALYSES["tariff"]
    return None  # noise items -> LLM "would" return NONE


# --------------------------------------------------------------------------- #
def make_news_items() -> list[NewsItem]:
    now = datetime.utcnow()
    items: list[NewsItem] = []
    for i, n in enumerate(SYNTHETIC_NEWS):
        published = now - timedelta(hours=i)
        url = f"https://example.com/news/{i}"
        items.append(
            NewsItem(
                id=content_hash(n["title"], url),
                source=n["source"],
                source_category=n["category"],
                source_region="global",
                title=n["title"],
                url=url,
                summary=n["summary"],
                body="",
                published_at=published,
            )
        )
    return items


# --------------------------------------------------------------------------- #
class StubMistralClient:
    """Drop-in replacement for ``LLMClient`` that returns pre-baked JSON."""

    provider = "ollama"
    model = "mistral"

    def complete(self, system: str, user: str) -> str:
        # Used by ReportGenerator for the executive summary - return prose.
        return (
            "Today's tape is dominated by a notably dovish shift across major "
            "central banks: the Fed's dot plot now points to two cuts in 2026, "
            "the ECB delivered a 25bp cut while signalling a pause, and the BoJ "
            "held but hinted at gradual normalisation. Soft US CPI at 2.4% YoY "
            "validated the disinflation narrative and pushed Treasury yields "
            "lower across the curve, with the dollar weakening modestly.\n\n"
            "Equities benefited unevenly. Tech leadership extended as Nvidia "
            "crossed the $4 trillion threshold and Apple's on-device AI chip "
            "supported services-revenue narratives. China's $200B property "
            "stimulus reignited reflation trades in industrial commodities and "
            "EM cyclicals.\n\n"
            "Risk-off cross-currents are worth flagging: an OPEC+ supply-cut "
            "extension and a Red Sea shipping incident pushed Brent above $87, "
            "and stalled US-EU auto-tariff talks weighed on European cyclicals.\n\n"
            "Outlook: cautiously bullish on US duration and tech, neutral on "
            "European cyclicals, mildly constructive on EM Asia."
        )

    def complete_json(self, system: str, user: str) -> dict | None:
        # Find which item this prompt is about by scanning for a known keyword
        u = user.lower()
        for key, payload in STUB_ANALYSES.items():
            tag = {
                "fed-hold": "federal reserve",
                "opec": "opec",
                "cpi": "cpi",
                "nvidia": "nvidia",
                "redsea": "red sea",
                "ecb": "ecb",
                "china": "china",
                "apple": "apple",
                "boj": "bank of japan",
                "tariff": "tariff",
            }[key]
            if tag in u:
                return payload
        return None  # unknown -> dropped


# --------------------------------------------------------------------------- #
def main() -> int:
    log.info("=" * 70)
    log.info("DEMO RUN: AI Market Intelligence Agent (Ollama Mistral simulation)")
    log.info("=" * 70)

    db = get_db()
    run_id = db.start_run()

    # 1. INGEST (synthetic)
    items = make_news_items()
    log.info(f"step 1/5: ingested {len(items)} synthetic news items")

    # 2. FILTER
    rf = RelevanceFilter(threshold=0.35)
    scored = rf.filter(items)
    log.info(f"step 2/5: relevance filter kept {len(scored)} / {len(items)} items")
    for s in scored:
        log.info(f"   score={s.relevance_score:.3f}  {s.item.title[:80]}")

    # 3. ANALYSE (stub Mistral)
    stub = StubMistralClient()
    analyzer = market_analyzer.MarketAnalyzerAgent(client=stub, max_workers=1)
    analyzed: list[AnalyzedEvent] = []
    for s in scored:
        ev = analyzer.analyze_one(s.item)
        if ev:
            analyzed.append(ev)
    # Re-apply analyzer's normal sort
    priority = {ImpactLevel.HIGH: 3, ImpactLevel.MEDIUM: 2, ImpactLevel.LOW: 1, ImpactLevel.NONE: 0}
    analyzed.sort(key=lambda e: (priority[e.analysis.impact_level], e.analysis.confidence), reverse=True)
    log.info(f"step 3/5: LLM analyzed {len(analyzed)} events")

    high, med, low = EventClassifier.split_by_impact(analyzed)
    log.info(f"           HIGH={len(high)}  MEDIUM={len(med)}  LOW={len(low)}")
    log.info(f"           sectors: {EventClassifier.sector_summary(analyzed)}")
    log.info(f"           assets:  {EventClassifier.asset_summary(analyzed)}")

    # 4. PERSIST
    db.save_events(analyzed)

    # 5. REPORT (also stubs the executive-summary LLM call)
    import src.reporting.report_generator as rg

    rg.get_llm_client = lambda: stub  # monkey-patch the module-level helper
    generator = ReportGenerator()
    report = generator.build(
        events=analyzed,
        total_items_collected=len(items),
        sources_used=sorted({e.item.source for e in analyzed}),
        date=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    artefacts = generator.render(report)
    html = artefacts["html"].read_text(encoding="utf-8")
    md = artefacts["markdown"].read_text(encoding="utf-8")
    db.save_report(report, html=html, markdown=md)
    db.finish_run(run_id, status="success", items_collected=len(items), items_analyzed=len(analyzed))

    log.info(f"step 5/5: report rendered to {artefacts['html'].parent}")
    log.info("=" * 70)
    log.info("DEMO RUN COMPLETE")
    log.info("=" * 70)

    print("\n=== SUMMARY ===")
    print(f"Items collected : {len(items)}")
    print(f"Items kept after filter: {len(scored)}")
    print(f"Items analyzed  : {len(analyzed)}")
    print(f"  HIGH impact   : {len(high)}")
    print(f"  MEDIUM impact : {len(med)}")
    print(f"Top sectors     : {dict(list(EventClassifier.sector_summary(analyzed).items())[:5])}")
    print(f"Top assets      : {dict(list(EventClassifier.asset_summary(analyzed).items())[:5])}")
    print(f"\nArtefacts:")
    for k, p in artefacts.items():
        print(f"  {k:9s} {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
