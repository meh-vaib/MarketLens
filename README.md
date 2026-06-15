# AI Market Intelligence Agent

> An autonomous AI system that collects global economic, financial, and geopolitical news, analyzes its potential impact on financial markets using LLMs, and delivers a professional daily intelligence report to investors.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Quick Start](#quick-start)
7. [Configuration](#configuration)
8. [Usage](#usage)
9. [Deployment](#deployment)
10. [Roadmap](#roadmap)
11. [License](#license)

---

## Overview

The **AI Market Intelligence Agent** is a modular, production-grade pipeline that automates the process of being an "always-on" market analyst. Every day it:

1. **Collects** news from (a) curated global RSS feeds (Reuters, CNBC, MarketWatch, FT, IMF, ECB, Fed, BoJ, etc.) and (b) the **GDELT Project DOC 2.0 API** — a free, key-less feed monitoring ~100,000 global news sources in 65+ languages, refreshing every 15 minutes.
2. **Filters** out noise using keyword heuristics and embedding-based relevance scoring.
3. **Analyzes** each story with a Large Language Model that reasons about likely market impact (direction, magnitude, time horizon, affected sectors and asset classes).
4. **Classifies** events on a structured taxonomy (HIGH / MEDIUM / LOW impact, sector tags, asset-class tags).
5. **Generates** an investor-grade daily report (HTML, Markdown, and PDF).
6. **Delivers** the report via email and exposes it through a FastAPI dashboard / REST endpoint.
7. **Runs** automatically on a schedule (APScheduler, cron, or Docker entrypoint).

The system is designed to run on free / minimal infrastructure: a single VM, a Raspberry Pi, GitHub Actions, or any container host.

---

## Architecture

### High-level flow

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  News Sources   │───▶│   Ingestion     │───▶│  Relevance       │
│  (RSS / APIs)   │    │   Orchestrator  │    │  Filter          │
└─────────────────┘    └─────────────────┘    └────────┬─────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Delivery      │◀───│   Reporting     │◀───│  LLM Market      │
│ (Email / API)   │    │   Generator     │    │  Analyzer Agent  │
└─────────────────┘    └─────────────────┘    └────────┬─────────┘
                              ▲                        │
                              │                        ▼
                       ┌──────┴──────────┐    ┌──────────────────┐
                       │   SQLite Store  │◀───│   Classifier     │
                       │  (events, runs) │    │ (impact/sector)  │
                       └─────────────────┘    └──────────────────┘
```

### Design decisions

| Decision | Rationale |
| --- | --- |
| **Python 3.11+** | Best-in-class ecosystem for data, LLMs, and async I/O. |
| **Modular package layout** | Each pipeline stage (ingestion, filtering, analysis, reporting, delivery) is a swappable component with a clear interface. |
| **Pydantic models** | Type-safe contracts between stages; eliminates a whole class of runtime bugs. |
| **APScheduler** | In-process daily scheduling with no external dependency; switchable to cron / Airflow. |
| **SQLite by default** | Zero-ops persistence for portfolios; trivially upgradable to Postgres via SQLAlchemy. |
| **Provider-agnostic LLM client** | Supports OpenAI, Anthropic, and local models (Ollama) behind one interface. |
| **Structured prompts** | Each prompt is versioned and stored under `src/analysis/prompts.py` so reasoning quality is reproducible. |
| **Loguru** | Better-than-stdlib logging with structured output and rotation out of the box. |
| **FastAPI** | Async web dashboard + REST API in ~50 lines, free Swagger UI. |
| **Docker** | One-command deploy on any host or free tier. |

---

## Features

- 20+ pre-configured global RSS feeds covering macro, equities, FX, commodities, central banks, and geopolitics.
- **GDELT Project integration** — 6 curated topical queries (macro, geopolitics, markets, earnings/M&A, tech/AI, energy/commodities) that pull from ~100k global sources every 15 minutes, with per-article country / language / source metadata. **No API key required.**
- Pluggable extra collectors for NewsAPI, FRED, AlphaVantage, and any custom REST endpoint.
- LLM-powered reasoning chain: *"What just happened?" → "Why does it matter?" → "What moves and by how much?"*
- Daily report in **HTML, Markdown, and PDF** formats.
- SMTP email delivery with rich HTML body.
- FastAPI dashboard (`/`), latest report endpoint (`/report/latest`), and JSON event stream (`/events`).
- Full deduplication (URL + content-hash) so stories aren't double-counted.
- Robust error handling: a failure in one collector never breaks the run.
- Structured logging with daily rotation.
- Unit-test scaffolding under `tests/`.
- Dockerfile + docker-compose for one-command deployment.

---

## Tech Stack

- **Language:** Python 3.11
- **LLM providers:** Anthropic Claude / OpenAI GPT / Groq (cloud, free tier) / Ollama (local, free)
- **Web framework:** FastAPI + Uvicorn
- **Scheduling:** APScheduler
- **Storage:** SQLite (via SQLAlchemy 2.x)
- **News parsing:** feedparser, httpx, beautifulsoup4
- **Templating:** Jinja2
- **PDF rendering:** WeasyPrint
- **Logging:** Loguru
- **Validation:** Pydantic v2
- **Config:** python-dotenv + YAML

---

## Project Structure

```
ai-market-intelligence/
├── README.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── config/
│   ├── __init__.py
│   ├── settings.py            # Pydantic-Settings driven configuration
│   └── sources.yaml           # Curated RSS / API sources
├── src/
│   ├── __init__.py
│   ├── main.py                # CLI entrypoint (run-once / serve / schedule)
│   ├── pipeline.py            # End-to-end orchestrator
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseCollector ABC
│   │   ├── rss_collector.py   # RSS fetcher
│   │   ├── gdelt_collector.py # GDELT DOC 2.0 fetcher (free, key-less)
│   │   ├── api_collector.py   # NewsAPI / generic REST fetcher
│   │   └── orchestrator.py    # Concurrent multi-source ingestion
│   ├── filtering/
│   │   ├── __init__.py
│   │   └── relevance_filter.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── llm_client.py      # Provider-agnostic LLM wrapper
│   │   ├── prompts.py         # Versioned prompt templates
│   │   └── market_analyzer.py # The "agent" that reasons about impact
│   ├── classification/
│   │   ├── __init__.py
│   │   └── classifier.py
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── report_generator.py
│   │   └── templates/
│   │       ├── daily_report.html
│   │       └── daily_report.md
│   ├── delivery/
│   │   ├── __init__.py
│   │   ├── email_sender.py
│   │   └── api_server.py      # FastAPI app
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── models.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── daily_scheduler.py
│   ├── schemas.py             # Pydantic data contracts
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── hashing.py
│       └── text.py
├── scripts/
│   ├── run_once.py
│   └── seed_sources.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_filtering.py
    ├── test_analyzer.py
    └── test_reporting.py
```

---

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/<your-username>/ai-market-intelligence.git
cd ai-market-intelligence
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# edit .env with your LLM API key + SMTP credentials

# 3. Run a single end-to-end pipeline (collect -> analyze -> report -> email)
python -m src.main run-once

# 4. OR run the daily scheduler (07:30 UTC by default)
python -m src.main schedule

# 5. OR serve the dashboard / API
python -m src.main serve
# then open http://localhost:8000
```

---

## Configuration

All settings are driven by environment variables (loaded from `.env`) plus `config/sources.yaml`. The most important keys:

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `anthropic` | One of `anthropic`, `openai`, `groq`, `ollama`. |
| `LLM_MODEL` | `claude-sonnet-4-6` | Provider-specific model name. |
| `ANTHROPIC_API_KEY` | – | Required if provider is `anthropic`. |
| `OPENAI_API_KEY` | – | Required if provider is `openai`. |
| `GROQ_API_KEY` | – | Required if provider is `groq` (free tier — recommended for hosted/GitHub Actions). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | For local model use. |
| `SMTP_HOST` / `SMTP_PORT` | – | Email delivery. |
| `SMTP_USER` / `SMTP_PASSWORD` | – | Email auth. |
| `EMAIL_FROM` / `EMAIL_TO` | – | Sender / recipient list (comma-separated). |
| `SCHEDULE_HOUR` / `SCHEDULE_MINUTE` | `7` / `30` | UTC time to run daily. |
| `DATABASE_URL` | `sqlite:///data/intel.db` | Any SQLAlchemy URL. |
| `MAX_ITEMS_PER_SOURCE` | `20` | Throttle per feed. |
| `MAX_ITEMS_TO_ANALYZE` | `25` | LLM cost control. |

To add or remove news sources, edit `config/sources.yaml` — no code changes needed. The file has three sections:

- `rss_sources` — direct RSS / Atom feeds (Reuters, Fed, ECB, …).
- `gdelt_sources` — GDELT DOC 2.0 queries. Each entry takes a `query`
  (full GDELT query syntax), a `timespan` (`24h` / `3d` / `1w`), an optional
  `country_filter` and `language_filter`, and a `category` for downstream tagging.
- `api_sources` — generic JSON / NewsAPI endpoints (off by default; gated by API key).

---

## Usage

### Run the pipeline once

```bash
python -m src.main run-once
```

Outputs:
- `data/reports/YYYY-MM-DD/report.html`
- `data/reports/YYYY-MM-DD/report.md`
- `data/reports/YYYY-MM-DD/report.pdf` (if WeasyPrint installed)
- Email sent to `EMAIL_TO`
- Events persisted to SQLite

### Serve the dashboard

```bash
python -m src.main serve --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /` – HTML dashboard with the latest report
- `GET /report/latest` – Latest report (HTML)
- `GET /report/{date}` – Historical report by ISO date
- `GET /events?limit=50` – Recent analyzed events as JSON
- `POST /run` – Trigger a pipeline run (requires `X-API-KEY` header)

### Schedule daily

```bash
python -m src.main schedule
```

Or use OS cron / systemd / Kubernetes CronJob to call `run_once.py`.

---

## Deployment

### Docker

```bash
docker compose up -d --build
```

The `app` service runs the scheduler; the `api` service exposes the dashboard on port 8000.

### GitHub Actions (free daily run + hosted website)

The repo ships three workflows in `.github/workflows/`:

- `ci.yml` — lint, format check, and tests on every push / PR.
- `daily-report.yml` — runs the full pipeline every day at 07:30 UTC, emails the report, and uploads it as an artifact.
- `pages.yml` — builds a static site from all generated reports and deploys it to GitHub Pages.

For a complete, zero-cost hosting walkthrough (free Groq LLM key, repository secrets, GitHub Pages setup), see **[HOSTING_GUIDE.md](HOSTING_GUIDE.md)**.

---

## Roadmap

- [ ] Vector store for semantic deduplication across days
- [ ] Trend tracking ("3rd day of hawkish Fed signals")
- [ ] Sentiment time-series per sector
- [ ] Slack & Telegram delivery channels
- [ ] Backtesting hooks against historical price data
- [ ] Web UI with filtering, search, and watchlists

---

## License

MIT © 2026 — Built as a portfolio-quality demonstration of agentic AI engineering.
