"""GDELT Project DOC API 2.0 collector.

GDELT (https://www.gdeltproject.org/) monitors broadcast, print, and web news
from across the world in 65+ languages, refreshes every 15 minutes, and
exposes a free, key-less HTTP API.

We use the DOC 2.0 ``ArtList`` mode which returns matching articles as JSON
records: ``url``, ``title``, ``seendate``, ``socialimage``, ``domain``,
``language``, ``sourcecountry``. That maps cleanly onto our ``NewsItem``.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

import httpx

from config import get_settings
from src.schemas import NewsItem
from src.utils import clean_text, content_hash, get_logger

from .base import BaseCollector

log = get_logger("gdelt")

# Default endpoint - the public, key-less DOC 2.0 API
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Serialize all GDELT requests to avoid 429s on the free, key-less API
_gdelt_semaphore = asyncio.Semaphore(1)
_GDELT_REQUEST_DELAY = 2.0  # seconds between requests


class GDELTCollector(BaseCollector):
    """Pull articles from the GDELT DOC 2.0 ArtList endpoint.

    Args:
        name: human-readable identifier for the source (used in reports/DB).
        query: GDELT query string. Supports the same syntax as
            https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
            e.g. ``"(inflation OR CPI OR \"interest rate\") sourcelang:eng"``.
        timespan: how far back to look (e.g. ``"24h"``, ``"3d"``, ``"1w"``).
        sort: ``"DateDesc"`` (newest first) or ``"HybridRel"`` (relevance).
        country_filter: optional ``sourcecountry:`` clause appended to query.
        language_filter: optional ``sourcelang:`` clause appended to query.
        category: pipeline-side category tag (macro / geopolitics / etc.).
    """

    def __init__(
        self,
        name: str,
        query: str,
        timespan: str = "24h",
        sort: str = "DateDesc",
        country_filter: Optional[str] = None,
        language_filter: Optional[str] = "eng",
        category: str = "general",
        region: str = "global",
    ) -> None:
        super().__init__(name=name, category=category, region=region)
        self.query = self._compose_query(query, country_filter, language_filter)
        self.timespan = timespan
        self.sort = sort

    # ------------------------------------------------------------------ #
    @staticmethod
    def _compose_query(query: str, country: Optional[str], language: Optional[str]) -> str:
        clauses = [query.strip()]
        if country:
            clauses.append(f"sourcecountry:{country}")
        if language and "sourcelang:" not in query:
            clauses.append(f"sourcelang:{language}")
        return " ".join(c for c in clauses if c)

    # ------------------------------------------------------------------ #
    async def fetch(self, limit: int) -> List[NewsItem]:
        settings = get_settings()
        params = {
            "query": self.query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": min(max(limit, 1), 250),  # API hard cap is 250
            "timespan": self.timespan,
            "sort": self.sort,
        }
        try:
            async with _gdelt_semaphore:
                async with httpx.AsyncClient(
                    timeout=settings.request_timeout_seconds,
                    follow_redirects=True,
                    headers={"User-Agent": "MarketIntelAgent/1.0 (gdelt-collector)"},
                ) as client:
                    resp = await client.get(GDELT_DOC_API, params=params)
                    resp.raise_for_status()
                    payload = resp.json()
                await asyncio.sleep(_GDELT_REQUEST_DELAY)
        except Exception as e:  # noqa: BLE001
            log.warning(f"[{self.name}] GDELT fetch failed: {e}")
            return []

        articles = payload.get("articles", []) or []
        items: List[NewsItem] = []
        for art in articles[:limit]:
            try:
                title = clean_text(art.get("title", ""))
                url = (art.get("url") or "").strip()
                if not title or not url:
                    continue
                published = _parse_seendate(art.get("seendate"))
                domain = art.get("domain") or ""
                language = art.get("language") or ""
                country = art.get("sourcecountry") or ""

                # GDELT has no body; build a summary from available metadata.
                summary_parts = [title]
                if domain:
                    summary_parts.append(f"(via {domain})")
                summary = " ".join(summary_parts)

                ident = content_hash(title, url)
                items.append(
                    NewsItem(
                        id=ident,
                        source=f"GDELT · {self.name}",
                        source_category=self.category,
                        source_region=country.lower() or self.region,
                        title=title,
                        url=url,
                        summary=summary,
                        body="",
                        published_at=published,
                    )
                )
            except Exception as e:  # noqa: BLE001
                log.debug(f"[{self.name}] skipping malformed GDELT record: {e}")

        log.info(f"[{self.name}] GDELT returned {len(items)} items "
                 f"(timespan={self.timespan})")
        return items


# --------------------------------------------------------------------------- #
def _parse_seendate(s: Optional[str]) -> Optional[datetime]:
    """GDELT ``seendate`` format is ``YYYYMMDDTHHMMSSZ``."""
    if not s:
        return None
    try:
        # e.g. "20260429T134500Z"
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ")
    except (ValueError, TypeError):
        # Some endpoints return ISO format instead - try that as a fallback.
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
