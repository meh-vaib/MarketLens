"""Convenience script: run the pipeline a single time."""
from __future__ import annotations

import sys
from pathlib import Path

# allow ``python scripts/run_once.py`` from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_pipeline  # noqa: E402


if __name__ == "__main__":
    result = run_pipeline()
    print(
        f"status={result.status} "
        f"collected={result.items_collected} "
        f"analyzed={result.items_analyzed} "
        f"date={result.report_date}"
    )
    sys.exit(0 if result.status == "success" else 1)
