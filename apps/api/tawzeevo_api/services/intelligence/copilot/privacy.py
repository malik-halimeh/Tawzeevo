"""Customer pseudonymization for provider egress (D-089).

A customer reference is `C-` plus six base32 characters of an HMAC over (tenant, conversation,
customer) keyed by the server secret. Within one Copilot conversation the same customer keeps the
same reference, so a follow-up can name it; a new conversation (new server-issued
`conversation_id`) gives every customer a fresh, unlinkable reference. Nothing is stored: the
client echoes the conversation id with its history. References resolve only inside Tawzeevo.

`mask`/`mask_value` are the single egress boundary: every text that leaves — the question, the
client-held history and every tool result string — passes through them, so a customer name that
appears in any free-text field (a product or manual line name, a category) is replaced too.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.models import Customer

REF_PATTERN = re.compile(r"\bC-[A-Z2-7]{6}\b")
MIN_NAME_LENGTH = 3  # shorter names are too likely to match ordinary words


def customer_ref(tenant_id: UUID, conversation_id: UUID, customer_id: UUID) -> str:
    key = get_settings().jwt_secret.encode("utf-8")
    message = f"copilot:{tenant_id}:{conversation_id}:{customer_id}".encode()
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return "C-" + base64.b32encode(digest).decode("ascii")[:6]


@dataclass
class CustomerDirectory:
    """The tenant's customers, loaded once per request; never sent anywhere."""

    tenant_id: UUID
    by_ref: dict[str, tuple[UUID, str]]
    ref_by_id: dict[UUID, str]
    _pattern: re.Pattern[str] | None
    _ref_by_name: dict[str, str]

    @classmethod
    def load(cls, db: Session, tenant_id: UUID, conversation_id: UUID) -> CustomerDirectory:
        by_ref: dict[str, tuple[UUID, str]] = {}
        ref_by_id: dict[UUID, str] = {}
        ref_by_name: dict[str, str] = {}
        for customer in db.scalars(
            select(Customer).where(Customer.tenant_id == tenant_id).order_by(Customer.id)
        ):
            ref = customer_ref(tenant_id, conversation_id, customer.id)
            by_ref[ref] = (customer.id, customer.name)
            ref_by_id[customer.id] = ref
            name = customer.name.strip()
            if len(name) >= MIN_NAME_LENGTH:
                # Two customers sharing one display name cannot be told apart from text; the
                # name is still masked (first reference wins) and never leaves the server.
                ref_by_name.setdefault(name.casefold(), ref)
        names = sorted(ref_by_name, key=len, reverse=True)
        pattern = (
            re.compile(
                r"(?<!\w)(" + "|".join(re.escape(n) for n in names) + r")(?!\w)", re.IGNORECASE
            )
            if names
            else None
        )
        return cls(tenant_id, by_ref, ref_by_id, pattern, ref_by_name)

    def ref(self, customer_id: UUID | None) -> str | None:
        return self.ref_by_id.get(customer_id) if customer_id is not None else None

    def resolve(self, ref: str) -> UUID | None:
        entry = self.by_ref.get(ref.strip().upper())
        return entry[0] if entry else None

    def mask(self, text: str) -> str:
        """Replace every known customer name with its reference before egress."""
        if self._pattern is None:
            return text
        return self._pattern.sub(lambda m: self._ref_by_name[m.group(1).casefold()], text)

    def mask_value(self, value: Any) -> Any:
        """Mask every string inside a JSON-like structure (keys are fixed code names)."""
        if isinstance(value, str):
            return self.mask(value)
        if isinstance(value, dict):
            return {key: self.mask_value(inner) for key, inner in value.items()}
        if isinstance(value, list):
            return [self.mask_value(inner) for inner in value]
        return value

    def unmask(self, text: str) -> tuple[str, list[str]]:
        """Replace references with display names (inside Tawzeevo only); unknown refs stay."""
        used: list[str] = []

        def swap(match: re.Match[str]) -> str:
            entry = self.by_ref.get(match.group(0))
            if entry is None:
                return match.group(0)
            if match.group(0) not in used:
                used.append(match.group(0))
            return entry[1]

        return REF_PATTERN.sub(swap, text), used
