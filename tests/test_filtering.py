from datetime import datetime

from src.filtering import RelevanceFilter
from src.schemas import NewsItem


def _make_item(title: str, summary: str = "") -> NewsItem:
    return NewsItem(
        id=title,
        source="test",
        title=title,
        url="https://example.com",
        summary=summary,
        published_at=datetime.utcnow(),
    )


def test_macro_news_passes_filter():
    f = RelevanceFilter(threshold=0.3)
    item = _make_item(
        "Federal Reserve hints at rate cut as inflation cools",
        summary="The FOMC signaled a possible 25 basis point cut next month.",
    )
    [scored] = f.filter([item])
    assert scored.relevance_score > 0.5


def test_irrelevant_news_filtered():
    f = RelevanceFilter(threshold=0.5)
    item = _make_item("Celebrity wedding draws huge crowd", summary="Fashion week recap")
    out = f.filter([item])
    assert out == []


def test_score_is_normalized_between_zero_and_one():
    f = RelevanceFilter(threshold=0.0)
    item = _make_item("OPEC, Fed, ECB, recession, oil price, inflation, tariff, war")
    [scored] = f.filter([item])
    assert 0.0 <= scored.relevance_score <= 1.0
