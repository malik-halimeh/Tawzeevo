"""Transactional e-mail behind one small adapter (D-077). The provider is selected by
`EMAIL_PROVIDER` and its credentials (`EMAIL_API_KEY`, `EMAIL_FROM`): Brevo or Resend on their
free tiers, otherwise the in-memory outbox used by tests and local runs (the message is logged
without its link). Nothing here retries or queues; a provider failure is reported to the caller,
never swallowed into a fake success."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from tawzeevo_api.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str


class MailerError(RuntimeError):
    pass


class MemoryMailer:
    """Test double: keeps sent messages in memory. Never used in production settings."""

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)
        logger.info("mail queued in memory outbox to=%s subject=%s", mail.to, mail.subject)


def split_sender(value: str) -> tuple[str, str]:
    """`Name <address>` or a bare address."""
    match = re.fullmatch(r"\s*(?:\"?([^\"<]*?)\"?\s*)?<([^<>\s]+)>\s*", value)
    if match:
        return (match.group(1) or "").strip() or "Tawzeevo", match.group(2)
    return "Tawzeevo", value.strip()


@dataclass
class BrevoMailer:
    api_key: str
    sender: str
    timeout: float = 10.0
    endpoint: str = field(default="https://api.brevo.com/v3/smtp/email")

    def send(self, mail: Mail) -> None:
        name, address = split_sender(self.sender)
        try:
            response = httpx.post(
                self.endpoint,
                headers={"api-key": self.api_key, "accept": "application/json"},
                json={
                    "sender": {"name": name, "email": address},
                    "to": [{"email": mail.to}],
                    "subject": mail.subject,
                    "textContent": mail.text,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MailerError("mail provider unreachable") from exc
        if response.status_code >= 300:
            raise MailerError(f"mail provider refused the message ({response.status_code})")


@dataclass
class ResendMailer:
    api_key: str
    sender: str
    timeout: float = 10.0
    endpoint: str = field(default="https://api.resend.com/emails")

    def send(self, mail: Mail) -> None:
        try:
            response = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": self.sender,
                    "to": [mail.to],
                    "subject": mail.subject,
                    "text": mail.text,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise MailerError("mail provider unreachable") from exc
        if response.status_code >= 300:
            raise MailerError(f"mail provider refused the message ({response.status_code})")


_memory = MemoryMailer()


def get_mailer(settings: Settings | None = None) -> MemoryMailer | BrevoMailer | ResendMailer:
    active = settings or get_settings()
    provider = active.email_provider.lower()
    if provider == "brevo" and active.email_api_key:
        return BrevoMailer(api_key=active.email_api_key, sender=active.email_from)
    if provider == "resend" and active.email_api_key:
        return ResendMailer(api_key=active.email_api_key, sender=active.email_from)
    return _memory


def memory_outbox() -> list[Mail]:
    return _memory.sent
