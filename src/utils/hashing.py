"""Stable hashing helpers for deduplication."""

from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")


def url_hash(url: str) -> str:
    """SHA-256 of the canonicalised URL."""
    canonical = url.strip().lower().rstrip("/")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def content_hash(*parts: str) -> str:
    """SHA-256 over normalised text fragments (title + body etc.)."""
    blob = " ".join(_WHITESPACE.sub(" ", (p or "").lower().strip()) for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
