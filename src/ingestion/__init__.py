"""News ingestion package."""
from .api_collector import NewsAPICollector
from .base import BaseCollector
from .gdelt_collector import GDELTCollector
from .orchestrator import IngestionOrchestrator
from .rss_collector import RSSCollector

__all__ = [
    "BaseCollector",
    "RSSCollector",
    "NewsAPICollector",
    "GDELTCollector",
    "IngestionOrchestrator",
]
