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
