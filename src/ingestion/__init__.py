"""News ingestion package."""
from .base import BaseCollector
from .rss_collector import RSSCollector
from .api_collector import NewsAPICollector
from .gdelt_collector import GDELTCollector
from .orchestrator import IngestionOrchestrator

__all__ = [
    "BaseCollector",
    "RSSCollector",
    "NewsAPICollector",
    "GDELTCollector",
    "IngestionOrchestrator",
]
