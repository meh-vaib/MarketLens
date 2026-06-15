"""CLI entrypoint.

Usage::

    python -m src.main run-once             # one full pipeline run
    python -m src.main schedule              # block forever, run daily
    python -m src.main serve [--host ... --port ...]   # FastAPI dashboard
"""
from __future__ import annotations

import argparse
import sys

from config import get_settings
from src.utils import get_logger, setup_logging


def _run_once(args: argparse.Namespace) -> int:  # noqa: ARG001
    from src.pipeline import run_pipeline

    result = run_pipeline()
    return 0 if result.status == "success" else 1


def _schedule(args: argparse.Namespace) -> int:  # noqa: ARG001
    from src.scheduler import run_scheduler

    run_scheduler()
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    settings = get_settings()
    host = args.host or settings.api_host
    port = args.port or settings.api_port
    uvicorn.run(
        "src.delivery.api_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    setup_logging(level=settings.log_level, log_dir=settings.log_dir)
    log = get_logger("main")

    parser = argparse.ArgumentParser(prog="market-intel")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run-once", help="Run the full pipeline a single time.")
    sub.add_parser("schedule", help="Run the daily scheduler in the foreground.")

    p_serve = sub.add_parser("serve", help="Run the FastAPI dashboard / API.")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)

    log.info(f"command: {args.cmd}")
    if args.cmd == "run-once":
        return _run_once(args)
    if args.cmd == "schedule":
        return _schedule(args)
    if args.cmd == "serve":
        return _serve(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
