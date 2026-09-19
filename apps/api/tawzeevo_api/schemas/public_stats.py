"""Public aggregate statistics (PHASE_08.md G; D-070)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PlatformStatsResponse(BaseModel):
    """Values are withheld (null) and `sufficient_data` is false below the D-070 thresholds."""

    sufficient_data: bool
    minimum_businesses: int
    minimum_customers: int
    active_businesses: int | None
    registered_customers: int | None
    published_products: int | None
    confirmed_invoices_last_30_days: int | None
    generated_at: datetime
