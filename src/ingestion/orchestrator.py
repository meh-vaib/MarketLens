"""Concurrent multi-source ingestion."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List

import yaml

from config.settings import SOURCES_FILE
from config import get_settings
from src.schemas import NewsItem
from src.utils import get_logger

from .api_collector import NewsAPICollector
from .base import BaseCollector
from .gdelt_collector import GDELTCollector
from .rss_collector import RSSCollector

log = get_logger("ingest")


class IngestionOrchestrator:
    """Loads sources from YAML and fetches them concurrently."""

    def __init__(self, sources_path: Path | None = None) -> None:
        self.sources_path = Path(sources_path) if sources_path else SOURCES_FILE
        self.collectors: List[BaseCollector] = self._load()

    # ---------------------------------------------------------------- #
    def _load(self) -> List[BaseCollector]:
        if not self.sources_path.exists():
            log.error(f"sources file not found: {self.sources_path}")
            return []
        with self.sources_path.open("r", encoding="utf-8") as f:
            cfg: Dict = yaml.safe_load(f) or {}

        collectors: List[BaseCollector] = []
        for src in cfg.get("rss_sources", []) or []:
            try:
                collectors.append(
                    RSSCollector(
                        name=src["name"],
                        url=src["url"],
                        category=src.get("category", "general"),
                        region=src.get("region", "global"),
                    )
                )
            except KeyError as e:
                log.warning(f"malformed RSS entry, missing {e}")

        for src in cfg.get("gdelt_sources", []) or []:
            if not src.get("enabled", True):
                continue
            try:
                collectors.append(
                    GDELTCollector(
                        name=src["name"],
                        query=src["query"],
                        timespan=src.get("timespan", "24h"),
                        sort=src.get("sort", "DateDesc"),
                        country_filter=src.get("country_filter"),
                        language_filter=src.get("language_filter", "eng"),
                        category=src.get("category", "general"),
                        region=src.get("region", "global"),
                    )
                )
            except KeyError as e:
                log.warning(f"malformed GDELT entry, missing {e}")

        for src in cfg.get("api_sources", []) or []:
            if not src.get("enabled", False):
                continue
            if src.get("type") == "newsapi":
                collectors.append(
                    NewsAPICollector(
                        name=src["name"],
                        endpoint=src["endpoint"],
                        params=src.get("params"),
                        api_key_env=src.get("api_key_env", "NEWSAPI_KEY"),
                        category=src.get("category", "general"),
                        region=src.get("region", "global"),
                    )
                )

        log.info(f"loaded {len(collectors)} collectors")
        return collectors

    # ---------------------------------------------------------------- #
    async def collect_all(self) -> List[NewsItem]:
        settings = get_settings()
        tasks = [c.fetch(settings.max_items_per_source) for c in self.collectors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items: List[NewsItem] = []
        seen_ids: set[str] = set()
        for res in results:
            if isinstance(res, Exception):
                log.warning(f"collector raised: {res}")
                continue
            for it in res:
                if it.id in seen_ids:
                    continue
                seen_ids.add(it.id)
                items.append(it)

        log.info(f"ingested {len(items)} unique items from {len(self.collectors)} sources")
        return items
