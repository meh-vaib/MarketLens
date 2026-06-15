"""Demo: GDELT collector with mocked HTTP response.

Proves the GDELT path works end-to-end (parse -> NewsItem -> filter) without
needing live network access. Useful for CI and offline demos.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("LLM_MODEL", "mistral")
os.environ.setdefault("EMAIL_ENABLED", "false")

import httpx  # noqa: E402

from src.ingestion import IngestionOrchestrator  # noqa: E402
from src.ingestion.gdelt_collector import GDELTCollector  # noqa: E402
from src.filtering import RelevanceFilter  # noqa: E402
from src.utils import get_logger, setup_logging  # noqa: E402

setup_logging("INFO")
log = get_logger("gdelt-demo")


def _make_gdelt_payload(category: str) -> dict:
    """Realistic GDELT-shaped payload tailored to the source category."""
    now = datetime.utcnow()

    def stamp(minutes_ago: int) -> str:
        return (now - timedelta(minutes=minutes_ago)).strftime("%Y%m%dT%H%M%SZ")

    samples = {
        "macro": [
            ("Federal Reserve holds rates steady, cites cooling inflation",
             "https://www.reuters.com/markets/us/fed-holds-rates", "reuters.com", "United States"),
            ("ECB delivers 25bp cut, Lagarde signals data-dependent path",
             "https://www.ft.com/content/ecb-cut", "ft.com", "United Kingdom"),
            ("US CPI cools to 2.4%, undershoots consensus",
             "https://www.bloomberg.com/news/cpi-cools", "bloomberg.com", "United States"),
            ("Bank of Japan keeps policy unchanged, hints at gradual normalisation",
             "https://www.nikkei.com/boj-update", "nikkei.com", "Japan"),
        ],
        "geopolitics": [
            ("OPEC+ extends voluntary production cuts through Q3 2026",
             "https://www.aljazeera.com/opec-extension", "aljazeera.com", "Qatar"),
            ("US-EU auto-tariff talks stall ahead of deadline",
             "https://www.dw.com/auto-tariff-talks", "dw.com", "Germany"),
            ("Red Sea shipping incident triggers re-routing surge",
             "https://www.bbc.com/news/red-sea", "bbc.com", "United Kingdom"),
        ],
        "markets": [
            ("Treasury yields fall as soft inflation print supports bonds",
             "https://www.cnbc.com/yields-fall", "cnbc.com", "United States"),
            ("S&P 500 closes at record on dovish Fed pivot",
             "https://www.marketwatch.com/sp500-record", "marketwatch.com", "United States"),
        ],
        "equities": [
            ("Nvidia tops $4 trillion market cap on AI sovereign deals",
             "https://www.barrons.com/nvidia-4t", "barrons.com", "United States"),
            ("Apple unveils on-device AI chip, services revenue acceleration eyed",
             "https://www.theverge.com/apple-m5", "theverge.com", "United States"),
        ],
        "commodities": [
            ("Brent climbs above $87 on supply-cut extension and Red Sea risk",
             "https://oilprice.com/brent-87", "oilprice.com", "United States"),
            ("Iron ore rallies 4% as China unveils $200B property stimulus",
             "https://www.scmp.com/iron-ore-rally", "scmp.com", "Hong Kong"),
        ],
    }

    rows = samples.get(category, [])
    return {
        "articles": [
            {
                "url": url,
                "title": title,
                "seendate": stamp(i * 25 + 5),
                "domain": domain,
                "language": "English",
                "sourcecountry": country,
            }
            for i, (title, url, domain, country) in enumerate(rows)
        ]
    }


class _MockTransport(httpx.AsyncBaseTransport):
    """Routes GDELT requests to category-specific mocked payloads."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("query", "").lower()
        if any(t in q for t in ["interest rate", "inflation", "federal reserve", "ecb", "cpi"]):
            cat = "macro"
        elif any(t in q for t in ["sanction", "tariff", "opec", "trade war", "ceasefire"]):
            cat = "geopolitics"
        elif any(t in q for t in ["stock market", "s&p 500", "nasdaq", "yield"]):
            cat = "markets"
        elif any(t in q for t in ["nvidia", "openai", "ai chip", "apple", "microsoft"]):
            cat = "equities"
        elif any(t in q for t in ["oil supply", "crude oil", "iron ore"]):
            cat = "commodities"
        elif any(t in q for t in ["earnings", "merger", "acquisition", "buyback"]):
            cat = "equities"
        else:
            cat = "macro"

        payload = _make_gdelt_payload(cat)
        return httpx.Response(
            200,
            content=json.dumps(payload).encode("utf-8"),
            request=request,
            headers={"Content-Type": "application/json"},
        )


async def main() -> int:
    print("\n" + "=" * 70)
    print("GDELT COLLECTOR DEMO  (mocked DOC 2.0 ArtList responses)")
    print("=" * 70)

    orch = IngestionOrchestrator()
    orch.collectors = [c for c in orch.collectors if isinstance(c, GDELTCollector)]
    print(f"Active collectors: {len(orch.collectors)} (GDELT only)\n")

    real_async_client = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs["transport"] = _MockTransport()
        return real_async_client(*args, **kwargs)

    with patch("src.ingestion.gdelt_collector.httpx.AsyncClient", patched):
        items = await orch.collect_all()

    print(f"\nIngested {len(items)} unique items from GDELT.\n")
    for it in items:
        when = it.published_at.strftime("%H:%M") if it.published_at else "-"
        print(f"  [{it.source_category:>11s}] {when}  {it.title[:78]}")
        print(f"               source={it.source}  region={it.source_region}")

    print("\n--- Pipeline-stage stats ---")
    rf = RelevanceFilter(threshold=0.35)
    scored = rf.filter(items)
    print(f"Relevance filter kept {len(scored)} / {len(items)} items")
    for s in scored[:5]:
        print(f"  score={s.relevance_score:.3f}  {s.item.title[:72]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
