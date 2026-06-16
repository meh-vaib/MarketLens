"""Tests for the GDELT DOC 2.0 collector.

Uses ``respx`` semantics via a custom monkey-patched httpx transport so we
don't have to add a new dependency. The mock response mirrors the actual
GDELT JSON payload shape.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest

from src.ingestion.gdelt_collector import GDELTCollector

# Real GDELT response shape (trimmed, with realistic field values)
SAMPLE_GDELT_RESPONSE = {
    "articles": [
        {
            "url": "https://www.reuters.com/markets/us/fed-cuts-rates-2026-04-29/",
            "url_mobile": "",
            "title": "Federal Reserve cuts rates by 25bps as inflation cools",
            "seendate": "20260429T134500Z",
            "socialimage": "https://www.reuters.com/img/r.jpg",
            "domain": "reuters.com",
            "language": "English",
            "sourcecountry": "United States",
        },
        {
            "url": "https://www.bloomberg.com/news/markets-rally",
            "title": "Markets rally on dovish Fed pivot",
            "seendate": "20260429T120000Z",
            "domain": "bloomberg.com",
            "language": "English",
            "sourcecountry": "United States",
        },
        {
            # Malformed entry - should be skipped
            "url": "",
            "title": "no url",
            "seendate": "20260429T120000Z",
        },
    ]
}


class _StubTransport(httpx.AsyncBaseTransport):
    """Pretend to be the GDELT API."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(self._payload).encode("utf-8"),
            request=request,
            headers={"Content-Type": "application/json"},
        )


@pytest.mark.asyncio
async def test_gdelt_collector_parses_articles():
    collector = GDELTCollector(
        name="Macro Test",
        query="inflation OR \"Federal Reserve\"",
        timespan="24h",
        category="macro",
    )

    transport = _StubTransport(SAMPLE_GDELT_RESPONSE)
    real_async_client = httpx.AsyncClient

    def patched_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    with patch("src.ingestion.gdelt_collector.httpx.AsyncClient", patched_async_client):
        items = await collector.fetch(limit=10)

    assert len(items) == 2  # malformed entry skipped
    assert items[0].title == "Federal Reserve cuts rates by 25bps as inflation cools"
    assert items[0].source.startswith("GDELT")
    assert items[0].source_category == "macro"
    assert items[0].published_at == datetime(2026, 4, 29, 13, 45, 0)
    assert items[0].url.startswith("https://www.reuters.com")
    assert items[1].title == "Markets rally on dovish Fed pivot"


def test_query_composition_appends_language_and_country():
    c = GDELTCollector(
        name="Test",
        query="inflation",
        country_filter="US",
        language_filter="eng",
    )
    assert "inflation" in c.query
    assert "sourcecountry:US" in c.query
    assert "sourcelang:eng" in c.query


def test_query_does_not_double_apply_language():
    c = GDELTCollector(
        name="Test",
        query="inflation sourcelang:eng",
        language_filter="eng",
    )
    # already in query - should not be appended again
    assert c.query.count("sourcelang:eng") == 1
