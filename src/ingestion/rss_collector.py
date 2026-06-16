"""RSS / Atom feed collector.

We use ``httpx`` for fetching (so the feed download itself is async-friendly)
and ``feedparser`` for parsing - feedparser is synchronous but extremely
robust against the chaos of real-world feeds.
"""
from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from config import get_settings
from src.schemas import NewsItem
from src.utils import clean_text, content_hash, get_logger

from .base import BaseCollector

log = get_logger("rss")


class RSSCollector(BaseCollector):
    def __init__(self, name: str, url: str, category: str = "general", region: str = "global"):
        super().__init__(name=name, category=category, region=region)
        self.url = url

    async def fetch(self, limit: int) -> list[NewsItem]:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(
                timeout=settings.request_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": "MarketIntelAgent/1.0 (+github.com/yours/ai-market-intelligence)"},
            ) as client:
                resp = await client.get(self.url)
                resp.raise_for_status()
                raw = resp.content
        except Exception as e:  # noqa: BLE001
            log.warning(f"[{self.name}] failed to fetch RSS: {e}")
            return []

        parsed = feedparser.parse(raw)
        items: list[NewsItem] = []
        for entry in parsed.entries[:limit]:
            try:
                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")
                if not title or not link:
                    continue
                summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
                published = _parse_date(entry)
                ident = content_hash(title, link)
                items.append(
                    NewsItem(
                        id=ident,
                        source=self.name,
                        source_category=self.category,
                        source_region=self.region,
                        title=title,
                        url=link,
                        summary=summary,
                        body="",
                        published_at=published,
                    )
                )
            except Exception as e:  # noqa: BLE001
                log.debug(f"[{self.name}] skipping malformed entry: {e}")
        log.info(f"[{self.name}] collected {len(items)} items")
        return items


def _parse_date(entry) -> datetime | None:
    for key in ("published", "updated", "created"):
        if entry.get(key):
            try:
                return parsedate_to_datetime(entry[key])
            except Exception:
                pass
    if entry.get("published_parsed"):
        try:
            return datetime(*entry["published_parsed"][:6])
        except Exception:
            return None
    return None
