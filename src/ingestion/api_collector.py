"""Generic JSON-API collector with first-class NewsAPI support."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

from config import get_settings
from src.schemas import NewsItem
from src.utils import clean_text, content_hash, get_logger

from .base import BaseCollector

log = get_logger("api")


class NewsAPICollector(BaseCollector):
    """Collector for https://newsapi.org/ (free tier supports 100 req/day)."""

    def __init__(
        self,
        name: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        api_key_env: str = "NEWSAPI_KEY",
        category: str = "general",
        region: str = "global",
    ) -> None:
        super().__init__(name=name, category=category, region=region)
        self.endpoint = endpoint
        self.params = dict(params or {})
        self.api_key = os.getenv(api_key_env, "")

    async def fetch(self, limit: int) -> list[NewsItem]:
        if not self.api_key:
            log.warning(f"[{self.name}] missing API key, skipping")
            return []
        params = {**self.params, "apiKey": self.api_key, "pageSize": limit}
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                resp = await client.get(self.endpoint, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as e:  # noqa: BLE001
            log.warning(f"[{self.name}] fetch failed: {e}")
            return []

        items: list[NewsItem] = []
        for art in payload.get("articles", [])[:limit]:
            title = clean_text(art.get("title", ""))
            url = art.get("url", "")
            if not title or not url:
                continue
            summary = clean_text(art.get("description", "") or "")
            body = clean_text(art.get("content", "") or "")
            published = _safe_iso(art.get("publishedAt"))
            ident = content_hash(title, url)
            items.append(
                NewsItem(
                    id=ident,
                    source=self.name,
                    source_category=self.category,
                    source_region=self.region,
                    title=title,
                    url=url,
                    summary=summary,
                    body=body,
                    published_at=published,
                )
            )
        log.info(f"[{self.name}] collected {len(items)} items")
        return items


def _safe_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
