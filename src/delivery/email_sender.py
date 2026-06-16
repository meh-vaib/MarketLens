"""SMTP email delivery."""
from __future__ import annotations

import smtplib
from collections.abc import Iterable
from email.message import EmailMessage
from pathlib import Path

from config import get_settings
from src.utils import get_logger

log = get_logger("email")


class EmailSender:
    """Thin wrapper around stdlib SMTP with TLS support."""

    def __init__(self) -> None:
        s = get_settings()
        self.host = s.smtp_host
        self.port = s.smtp_port
        self.user = s.smtp_user
        self.password = s.smtp_password
        self.email_from = s.email_from
        self.email_to: list[str] = s.email_to
        self.enabled = s.email_enabled

    # ------------------------------------------------------------------ #
    def is_configured(self) -> bool:
        return bool(
            self.enabled
            and self.host
            and self.user
            and self.password
            and self.email_from
            and self.email_to
        )

    # ------------------------------------------------------------------ #
    def send_report(
        self,
        subject: str,
        html: str,
        markdown_text: str | None = None,
        attachments: Iterable[Path] | None = None,
    ) -> bool:
        if not self.is_configured():
            log.warning("email not configured / disabled - skipping")
            return False

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = ", ".join(self.email_to)

        msg.set_content(markdown_text or "Please view this email in HTML.")
        msg.add_alternative(html, subtype="html")

        for path in attachments or []:
            try:
                path = Path(path)
                data = path.read_bytes()
                maintype, subtype = _guess_mime(path)
                msg.add_attachment(
                    data, maintype=maintype, subtype=subtype, filename=path.name
                )
            except Exception as e:  # noqa: BLE001
                log.warning(f"failed to attach {path}: {e}")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.ehlo()
                if self.port in (587, 25):
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(self.user, self.password)
                smtp.send_message(msg)
            log.info(f"sent report email to {len(self.email_to)} recipients")
            return True
        except Exception as e:  # noqa: BLE001
            log.error(f"email send failed: {e}")
            return False


def _guess_mime(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return ("text", "html")
    if suffix == ".md":
        return ("text", "markdown")
    if suffix == ".pdf":
        return ("application", "pdf")
    if suffix == ".txt":
        return ("text", "plain")
    return ("application", "octet-stream")
