"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make ``src`` and ``config`` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force a temporary, isolated DB during tests
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("EMAIL_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("OPENAI_API_KEY", "test")
