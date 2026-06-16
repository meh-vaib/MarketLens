"""Pre-LLM relevance filter.

We don't want to spend an LLM call on every celebrity story or sports
headline. This filter computes a cheap keyword-based relevance score and
discards items below the configured threshold.

The keyword lexicon is intentionally broad and weighted, so it acts as a
recall-friendly first pass. The LLM is the precision layer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.schemas import NewsItem, ScoredNewsItem

# Domain-specific lexicons. Higher weight => stronger relevance signal.
LEXICON: dict[str, float] = {
    # Macro
    "inflation": 1.0,
    "cpi": 1.0,
    "ppi": 0.9,
    "gdp": 1.0,
    "unemployment": 0.9,
    "jobs report": 1.0,
    "non-farm payroll": 1.0,
    "nonfarm": 1.0,
    "recession": 1.2,
    "stagflation": 1.2,
    "deflation": 0.9,
    "yield curve": 1.0,
    "monetary policy": 1.0,
    "fiscal policy": 0.8,
    "trade deficit": 0.7,
    "treasury": 0.8,
    # Central banks
    "federal reserve": 1.2,
    "fed ": 1.0,
    "fomc": 1.2,
    "ecb": 1.1,
    "bank of japan": 1.1,
    "boj": 1.0,
    "bank of england": 1.0,
    "boe": 0.8,
    "rate hike": 1.2,
    "rate cut": 1.2,
    "interest rate": 1.0,
    "basis point": 0.9,
    "hawkish": 1.0,
    "dovish": 1.0,
    "quantitative easing": 1.1,
    # Markets
    "stock market": 0.9,
    "equities": 0.9,
    "s&p 500": 1.0,
    "nasdaq": 1.0,
    "dow jones": 0.9,
    "ftse": 0.8,
    "nikkei": 0.8,
    "hang seng": 0.8,
    "bond yield": 1.0,
    "sovereign debt": 1.0,
    "credit spread": 0.9,
    "currency": 0.8,
    "forex": 0.8,
    "fx": 0.6,
    "dollar": 0.7,
    "euro": 0.7,
    "yen": 0.7,
    "commodity": 0.8,
    "commodities": 0.8,
    "oil price": 1.0,
    "brent": 0.9,
    "wti": 0.9,
    "gold": 0.8,
    "natural gas": 0.8,
    "copper": 0.7,
    "earnings": 0.9,
    "guidance": 0.7,
    "ipo": 0.8,
    "merger": 0.8,
    "acquisition": 0.8,
    "buyback": 0.7,
    "dividend": 0.6,
    "bankruptcy": 1.0,
    # Geopolitics
    "war": 1.0,
    "sanction": 1.0,
    "tariff": 1.1,
    "trade war": 1.2,
    "embargo": 0.9,
    "election": 0.8,
    "geopolitical": 0.9,
    "ceasefire": 0.8,
    "opec": 1.0,
    # Crypto
    "bitcoin": 0.7,
    "ethereum": 0.6,
    "crypto": 0.7,
    "stablecoin": 0.7,
    # Tech / corporates that move indices
    "apple": 0.5,
    "microsoft": 0.5,
    "nvidia": 0.6,
    "tesla": 0.5,
    "amazon": 0.5,
    "alphabet": 0.5,
    "google": 0.4,
    "meta": 0.5,
    "openai": 0.4,
    # India: indices, regulators, currency & bellwether names
    "nifty": 1.2,
    "sensex": 1.2,
    "nse": 1.0,
    "bse": 1.0,
    "dalal street": 1.0,
    "nifty 50": 1.2,
    "bank nifty": 1.1,
    "reserve bank of india": 1.2,
    "rbi": 1.2,
    "sebi": 1.0,
    "rupee": 1.0,
    "inr": 0.8,
    "repo rate": 1.0,
    "mpc": 0.9,
    "indian economy": 1.0,
    "indian markets": 1.0,
    "fii": 0.9,
    "dii": 0.9,
    "reliance": 0.7,
    "tata": 0.6,
    "infosys": 0.7,
    "tcs": 0.7,
    "hdfc": 0.7,
    "adani": 0.7,
    "icici": 0.6,
    "gst": 0.7,
    "union budget": 1.0,
}

NEGATIVE_LEXICON = {
    "celebrity",
    "kardashian",
    "movie review",
    "soccer",
    "football match",
    "basketball game",
    "fashion week",
    "horoscope",
}


class RelevanceFilter:
    """Score and filter news items for macro / market relevance."""

    def __init__(self, threshold: float = 0.35):
        self.threshold = threshold
        # pre-compile regex per keyword for speed
        self._patterns = [
            (re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE), w) for k, w in LEXICON.items()
        ]
        self._negative = [
            re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE) for k in NEGATIVE_LEXICON
        ]

    # ---------------------------------------------------------------- #
    def score(self, item: NewsItem) -> ScoredNewsItem:
        text = f"{item.title}\n{item.summary or ''}"
        if any(p.search(text) for p in self._negative):
            return ScoredNewsItem(item=item, relevance_score=0.0, matched_keywords=[])

        matched: list[str] = []
        score = 0.0
        for pattern, weight in self._patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)
                score += weight

        # Title hits count more
        title_lower = item.title.lower()
        title_bonus = sum(0.5 for k in LEXICON if k in title_lower)
        score += title_bonus

        # Soft-cap & normalise so threshold values stay intuitive (0..1ish)
        normalised = 1 - (1 / (1 + score))  # logistic-ish squashing
        return ScoredNewsItem(item=item, relevance_score=normalised, matched_keywords=matched)

    def filter(self, items: Iterable[NewsItem]) -> list[ScoredNewsItem]:
        scored = [self.score(i) for i in items]
        kept = [s for s in scored if s.relevance_score >= self.threshold]
        kept.sort(key=lambda s: s.relevance_score, reverse=True)
        return kept
