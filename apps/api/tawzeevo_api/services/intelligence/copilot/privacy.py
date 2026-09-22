"""Customer pseudonymization for provider egress (D-089).

A customer reference is `C-` plus six base32 characters of an HMAC over (tenant, customer) keyed
by the server secret: opaque to the provider, stable across a client-held conversation so a
follow-up question can name the same customer, and resolvable only inside Tawzeevo. Before any
text leaves, every known customer name of the tenant is replaced by its reference; after the
answer returns, references are replaced by names for display only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.models import Customer

REF_PATTERN = re.compile(r"\bC-[A-Z2-7]{6}\b")
MIN_NAME_LENGTH = 3  # shorter names are too likely to match ordinary words


def customer_ref(tenant_id: UUID, customer_id: UUID) -> str:
    key = get_settings().jwt_secret.encode("utf-8")
    digest = hmac.new(key, f"copilot:{tenant_id}:{customer_id}".encode(), hashlib.sha256).digest()
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
    def load(cls, db: Session, tenant_id: UUID) -> CustomerDirectory:
        by_ref: dict[str, tuple[UUID, str]] = {}
        ref_by_id: dict[UUID, str] = {}
        ref_by_name: dict[str, str] = {}
        for customer in db.scalars(
            select(Customer).where(Customer.tenant_id == tenant_id).order_by(Customer.id)
        ):
            ref = customer_ref(tenant_id, customer.id)
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
