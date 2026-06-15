"""Pydantic data contracts shared across the pipeline.

Every stage takes & returns one of these models, which makes the system easy
to test and refactor.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class ImpactLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ImpactDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"


class TimeHorizon(str, Enum):
    INTRADAY = "INTRADAY"
    SHORT_TERM = "SHORT_TERM"   # days
    MEDIUM_TERM = "MEDIUM_TERM" # weeks
    LONG_TERM = "LONG_TERM"     # months+


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
class NewsItem(BaseModel):
    """A single raw news item collected from any source."""

    id: str  # content hash
    source: str
    source_category: Optional[str] = None
    source_region: Optional[str] = None
    title: str
    url: str
    summary: Optional[str] = ""
    body: Optional[str] = ""
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
class ScoredNewsItem(BaseModel):
    item: NewsItem
    relevance_score: float
    matched_keywords: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# LLM analysis
# --------------------------------------------------------------------------- #
class MarketAnalysis(BaseModel):
    """Structured output of the LLM market-impact agent."""

    headline: str
    summary: str = Field(..., description="2-3 sentence neutral summary of the event.")
    why_it_matters: str = Field(..., description="Why investors should care.")
    impact_level: ImpactLevel
    impact_direction: ImpactDirection
    time_horizon: TimeHorizon
    affected_sectors: List[str] = Field(default_factory=list)
    affected_assets: List[str] = Field(default_factory=list)  # e.g. ["USD", "Gold", "SPX"]
    affected_regions: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = Field("", description="Short reasoning chain from the LLM.")


class AnalyzedEvent(BaseModel):
    """A news item after relevance filtering and LLM analysis."""

    item: NewsItem
    analysis: MarketAnalysis
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
class DailyReport(BaseModel):
    date: str  # ISO date
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    executive_summary: str
    market_outlook: str
    high_impact_events: List[AnalyzedEvent] = Field(default_factory=list)
    medium_impact_events: List[AnalyzedEvent] = Field(default_factory=list)
    sector_summary: dict = Field(default_factory=dict)  # sector -> count
    asset_summary: dict = Field(default_factory=dict)   # asset -> count
    sources_used: List[str] = Field(default_factory=list)
    total_items_collected: int = 0
    total_items_analyzed: int = 0
