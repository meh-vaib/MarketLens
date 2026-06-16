"""Lightweight text helpers (no heavy NLP deps)."""

from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(html_or_text: str | None) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not html_or_text:
        return ""
    text = _TAG_RE.sub(" ", html_or_text)
    text = unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def truncate(text: str, max_chars: int = 600, ellipsis: str = "…") -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(ellipsis)].rstrip() + ellipsis


def summarize_text(text: str, max_sentences: int = 2) -> str:
    """Return the first ``max_sentences`` sentences of ``text``."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences]).strip()


# --------------------------------------------------------------------------- #
# Near-duplicate detection
# --------------------------------------------------------------------------- #
# Common words that carry no signal when comparing headlines for similarity.
_STOPWORDS = frozenset("""
    a an and as at be but by for from has have in into is it its of on or that
    the to vs was were will with after over amid says say said new news report
    reports update updates breaking live latest
    """.split())
_WORD_RE = re.compile(r"[a-z0-9]+")


def title_tokens(title: str) -> frozenset[str]:
    """Significant lowercase word tokens of a headline (stopwords removed)."""
    words = _WORD_RE.findall((title or "").lower())
    return frozenset(w for w in words if w not in _STOPWORDS and len(w) > 2)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity (size of intersection / size of union) of two sets."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)
