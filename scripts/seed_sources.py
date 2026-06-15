"""Sanity check: load the configured sources and print a summary."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion import IngestionOrchestrator  # noqa: E402


if __name__ == "__main__":
    orch = IngestionOrchestrator()
    print(f"Loaded {len(orch.collectors)} collectors:")
    for c in orch.collectors:
        print(f"  - [{c.category:>12}] {c.name}")
