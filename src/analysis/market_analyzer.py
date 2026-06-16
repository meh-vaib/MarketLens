"""The market-impact analyzer agent.

Each news item is reasoned about by an LLM following a structured prompt
(see ``prompts.py``). The LLM returns a JSON object that we validate against
:class:`src.schemas.MarketAnalysis`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import ValidationError

from src.schemas import (
    AnalyzedEvent,
    ImpactDirection,
    ImpactLevel,
    MarketAnalysis,
    NewsItem,
    ScoredNewsItem,
    TimeHorizon,
)
from src.utils import get_logger, truncate

from .llm_client import LLMClient, get_llm_client
from .prompts import ANALYZER_SYSTEM_PROMPT, ANALYZER_USER_TEMPLATE

log = get_logger("analyzer")


class MarketAnalyzerAgent:
    """LLM-powered market impact analyst."""

    # Free-tier hosted APIs and local single-GPU Ollama choke on parallelism,
    # so cap concurrency per provider to stay under rate limits.
    _PROVIDER_WORKERS = {"groq": 1, "ollama": 1, "openai": 4, "anthropic": 4}

    def __init__(self, client: LLMClient | None = None, max_workers: int | None = None) -> None:
        self.client = client or get_llm_client()
        if max_workers is None:
            max_workers = self._PROVIDER_WORKERS.get(self.client.provider, 2)
        self.max_workers = max_workers

    # ------------------------------------------------------------------ #
    def analyze_one(self, item: NewsItem) -> AnalyzedEvent | None:
        prompt = ANALYZER_USER_TEMPLATE.format(
            title=item.title,
            source=item.source,
            published=item.published_at.isoformat() if item.published_at else "unknown",
            url=item.url,
            summary=truncate(item.summary or item.title, 1500),
        )

        data = self.client.complete_json(ANALYZER_SYSTEM_PROMPT, prompt)
        if not data:
            return None

        try:
            analysis = MarketAnalysis(**self._coerce(data, item))
        except ValidationError as e:
            log.warning(f"validation failed for '{item.title[:80]}': {e}")
            return None

        if analysis.impact_level == ImpactLevel.NONE:
            return None  # filter out items the LLM judged irrelevant

        return AnalyzedEvent(item=item, analysis=analysis)

    # ------------------------------------------------------------------ #
    def analyze_many(self, scored: list[ScoredNewsItem]) -> list[AnalyzedEvent]:
        """Analyse a batch of pre-filtered items concurrently."""
        results: list[AnalyzedEvent] = []
        if not scored:
            return results

        total = len(scored)
        done = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self.analyze_one, s.item): s for s in scored}
            for fut in as_completed(futures):
                done += 1
                try:
                    ev = fut.result()
                    if ev:
                        results.append(ev)
                except Exception as e:  # noqa: BLE001
                    log.warning(f"analyzer worker failed: {e}")
                if done % 5 == 0 or done == total:
                    log.info(f"  analyzed {done}/{total} items")

        # Sort by impact_level desc, then confidence desc
        priority = {
            ImpactLevel.HIGH: 3,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.LOW: 1,
            ImpactLevel.NONE: 0,
        }
        results.sort(
            key=lambda e: (priority[e.analysis.impact_level], e.analysis.confidence),
            reverse=True,
        )
        log.info(f"analyzed {len(results)} events")
        return results

    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce(data: dict, item: NewsItem) -> dict:
        """Normalise LLM output to match our enums (fault-tolerant)."""
        out = dict(data)
        out.setdefault("headline", item.title)
        out.setdefault("summary", item.summary or item.title)
        out.setdefault("why_it_matters", "")
        out.setdefault("rationale", "")
        out.setdefault("affected_sectors", [])
        out.setdefault("affected_assets", [])
        out.setdefault("affected_regions", [])
        out.setdefault("confidence", 0.5)

        # enum normalisation
        out["impact_level"] = _norm_enum(out.get("impact_level"), ImpactLevel, ImpactLevel.NONE)
        out["impact_direction"] = _norm_enum(
            out.get("impact_direction"), ImpactDirection, ImpactDirection.NEUTRAL
        )
        out["time_horizon"] = _norm_enum(
            out.get("time_horizon"), TimeHorizon, TimeHorizon.SHORT_TERM
        )
        try:
            c = float(out["confidence"])
            out["confidence"] = max(0.0, min(1.0, c))
        except (TypeError, ValueError):
            out["confidence"] = 0.5
        return out


def _norm_enum(value, enum_cls, default):
    if value is None:
        return default
    try:
        return enum_cls(str(value).upper())
    except ValueError:
        return default
