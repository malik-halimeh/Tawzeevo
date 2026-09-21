"""Provider-neutral one-time-code delivery (D-073). The domain never depends on WhatsApp or SMS:
it asks this adapter to deliver a code to a phone number and gets success or `DeliveryUnavailable`.
Only the development adapter exists until the owner selects a production provider at the gate
(PHASE_09.md P9-M5 precondition); it keeps codes in memory for tests and local runs and never
prints them to the log."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from tawzeevo_api.config import Settings, get_settings

logger = logging.getLogger(__name__)


class DeliveryUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OtpMessage:
    phone: str
    code: str
    language: str
    business_name: str


class OtpDelivery(Protocol):
    channel: str

    def send(self, message: OtpMessage) -> None: ...


class DevOtpDelivery:
    """Test/local double: remembers the latest code per phone; nothing leaves the process."""

    channel = "dev"

    def __init__(self) -> None:
        self._latest: dict[str, str] = {}
        self._lock = Lock()
        self.fail_next = False

    def send(self, message: OtpMessage) -> None:
        if self.fail_next:
            self.fail_next = False
            raise DeliveryUnavailable("simulated provider outage")
        with self._lock:
            self._latest[message.phone] = message.code
        logger.info("dev otp delivered channel=dev business=%s", message.business_name)

    def latest_code(self, phone: str) -> str | None:
        with self._lock:
            return self._latest.get(phone)


class UnconfiguredDelivery:
    """A production channel named in settings without an implemented, credentialed adapter."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def send(self, message: OtpMessage) -> None:
        raise DeliveryUnavailable(f"otp provider '{self.channel}' is not configured")


_dev = DevOtpDelivery()


def get_otp_delivery(settings: Settings | None = None) -> OtpDelivery:
    active = settings or get_settings()
    provider = active.customer_otp_provider.lower()
    if provider == "dev":
        return _dev
    return UnconfiguredDelivery(provider)


def delivery_is_usable(settings: Settings | None = None) -> bool:
    """Can a one-time code actually reach a customer with this configuration? The development
    adapter only counts outside production (it never leaves the process); an unimplemented or
    uncredentialed production channel never counts. Policies that depend on delivery (VERIFIED)
    are only selectable when this is true, so a business cannot lock its customers out."""
    active = settings or get_settings()
    provider = active.customer_otp_provider.lower()
    if provider == "dev":
        return active.app_env.lower() != "production"
    return False  # no production adapter is implemented yet (P9-M5 provider decision pending)


def dev_delivery() -> DevOtpDelivery:
    return _dev
