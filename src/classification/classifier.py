"""Event classifier / aggregator.

The LLM already labels each event individually. This module adds aggregate
views (counts by sector, asset, region, impact level) used by the report
generator and downstream analytics.
"""

from __future__ import annotations

from collections import Counter

from src.schemas import AnalyzedEvent, ImpactLevel


class EventClassifier:
    @staticmethod
    def split_by_impact(
        events: list[AnalyzedEvent],
    ) -> tuple[list[AnalyzedEvent], list[AnalyzedEvent], list[AnalyzedEvent]]:
        high = [e for e in events if e.analysis.impact_level == ImpactLevel.HIGH]
        med = [e for e in events if e.analysis.impact_level == ImpactLevel.MEDIUM]
        low = [e for e in events if e.analysis.impact_level == ImpactLevel.LOW]
        return high, med, low

    @staticmethod
    def sector_summary(events: list[AnalyzedEvent]) -> dict[str, int]:
        c: Counter = Counter()
        for e in events:
            for s in e.analysis.affected_sectors:
                if s:
                    c[s.strip()] += 1
        return dict(c.most_common())

    @staticmethod
    def asset_summary(events: list[AnalyzedEvent]) -> dict[str, int]:
        c: Counter = Counter()
        for e in events:
            for a in e.analysis.affected_assets:
                if a:
                    c[a.strip()] += 1
        return dict(c.most_common())

    @staticmethod
    def region_summary(events: list[AnalyzedEvent]) -> dict[str, int]:
        c: Counter = Counter()
        for e in events:
            for r in e.analysis.affected_regions:
                if r:
                    c[r.strip()] += 1
        return dict(c.most_common())
