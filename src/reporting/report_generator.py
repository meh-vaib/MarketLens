"""Render the daily report into HTML, Markdown, and (optionally) PDF."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import REPORT_DIR
from src.analysis import get_llm_client
from src.analysis.prompts import EXEC_SUMMARY_SYSTEM_PROMPT, EXEC_SUMMARY_USER_TEMPLATE
from src.classification import EventClassifier
from src.schemas import AnalyzedEvent, DailyReport
from src.utils import get_logger, truncate

log = get_logger("report")

TEMPLATES_DIR = Path(__file__).parent / "templates"


class ReportGenerator:
    """Builds a :class:`DailyReport` and renders it to disk."""

    def __init__(self, output_dir: Path = REPORT_DIR) -> None:
        self.output_dir = Path(output_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ------------------------------------------------------------------ #
    def build(
        self,
        events: list[AnalyzedEvent],
        *,
        total_items_collected: int,
        sources_used: list[str],
        date: str | None = None,
    ) -> DailyReport:
        date = date or datetime.utcnow().strftime("%Y-%m-%d")
        high, med, _low = EventClassifier.split_by_impact(events)

        executive_summary = self._executive_summary(date, high + med)
        market_outlook = ""

        report = DailyReport(
            date=date,
            generated_at=datetime.utcnow(),
            executive_summary=executive_summary,
            market_outlook=market_outlook,
            high_impact_events=high,
            medium_impact_events=med,
            sector_summary=EventClassifier.sector_summary(events),
            asset_summary=EventClassifier.asset_summary(events),
            sources_used=sources_used,
            total_items_collected=total_items_collected,
            total_items_analyzed=len(events),
        )
        return report

    # ------------------------------------------------------------------ #
    def render(self, report: DailyReport) -> dict[str, Path]:
        """Render the report and return the paths of the generated files."""
        out_dir = self.output_dir / report.date
        out_dir.mkdir(parents=True, exist_ok=True)

        html = self.env.get_template("daily_report.html").render(report=report)
        md = self.env.get_template("daily_report.md").render(report=report)

        html_path = out_dir / "report.html"
        md_path = out_dir / "report.md"
        html_path.write_text(html, encoding="utf-8")
        md_path.write_text(md, encoding="utf-8")

        artefacts = {"html": html_path, "markdown": md_path}

        # Optional PDF (skipped silently if WeasyPrint unavailable)
        try:
            from weasyprint import HTML  # type: ignore

            pdf_path = out_dir / "report.pdf"
            HTML(string=html).write_pdf(str(pdf_path))
            artefacts["pdf"] = pdf_path
        except Exception as e:  # noqa: BLE001
            log.debug(f"PDF rendering skipped: {e}")

        log.info(f"report rendered for {report.date} -> {out_dir}")
        return artefacts

    # ------------------------------------------------------------------ #
    def _executive_summary(self, date: str, events: list[AnalyzedEvent]) -> str:
        if not events:
            return (
                "No high- or medium-impact market-moving stories were detected today. "
                "Markets are likely to trade on positioning and existing catalysts. "
                "Outlook: neutral."
            )

        block_lines = []
        for i, e in enumerate(events[:15], 1):
            block_lines.append(
                f"{i}. [{e.analysis.impact_level.value} / {e.analysis.impact_direction.value}] "
                f"{e.analysis.headline or e.item.title} -- {truncate(e.analysis.summary, 240)}"
            )
        events_block = "\n".join(block_lines)

        prompt = EXEC_SUMMARY_USER_TEMPLATE.format(date=date, events_block=events_block)
        try:
            text = get_llm_client().complete(EXEC_SUMMARY_SYSTEM_PROMPT, prompt).strip()
        except Exception as e:  # noqa: BLE001
            log.warning(f"executive summary LLM call failed: {e}")
            text = ""
        if not text:
            text = self._fallback_summary(events)
        return text

    @staticmethod
    def _fallback_summary(events: list[AnalyzedEvent]) -> str:
        bull = sum(1 for e in events if e.analysis.impact_direction.value == "BULLISH")
        bear = sum(1 for e in events if e.analysis.impact_direction.value == "BEARISH")
        bias = "bullish" if bull > bear else "bearish" if bear > bull else "mixed"
        top = events[0]
        return (
            f"Today's tape is dominated by {len(events)} market-relevant stories, with a "
            f"{bias} skew. Headline event: {top.analysis.headline or top.item.title}. "
            f"{top.analysis.why_it_matters} Outlook: {bias}."
        )
