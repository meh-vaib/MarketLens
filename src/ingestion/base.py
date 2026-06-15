"""Abstract base class for any news collector."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.schemas import NewsItem


class BaseCollector(ABC):
    """Common interface for all news source collectors."""

    name: str = "base"
    category: str = "general"
    region: str = "global"

    def __init__(self, name: str, category: str = "general", region: str = "global") -> None:
        self.name = name
        self.category = category
        self.region = region

    @abstractmethod
    async def fetch(self, limit: int) -> List[NewsItem]:
        """Return up to ``limit`` items from this source."""
