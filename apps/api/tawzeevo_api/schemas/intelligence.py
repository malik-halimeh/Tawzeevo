"""Owner-only intelligence API shapes (D-089). Every money figure travels with its currency, lists
are grouped per currency and nothing is summed across currencies. Scores and bands are workflow
heuristics, never probabilities; cash-flow carries no forecast field."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from tawzeevo_api.schemas.analytics import PeriodInfo

Scalar = Decimal | int | str | bool | None


class Reason(BaseModel):
    code: str
    value: Scalar = None
    context: dict[str, Scalar] = {}


class PriorityComponents(BaseModel):
    """Points earned per component; null = inputs unavailable (excluded from the denominator)."""

    collection_urgency: int | None
    relationship_inactivity: int | None
    activity_decline: int | None
    friction_signals: int | None


class PriorityItem(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_grade: str | None
    currency: str
    score: int
    band: str
    components: PriorityComponents
    reasons: list[Reason]
    suggested_action_code: str
    inactivity_status: str
    outstanding_balance: Decimal
    days_since_last_purchase: int | None


class PriorityGroup(BaseModel):
    currency: str
    items: list[PriorityItem]


class PrioritiesResponse(BaseModel):
    as_of: datetime
    groups: list[PriorityGroup]


class InactivityItem(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_grade: str | None
    currency: str
    status: str
    recency_ratio: Decimal | None
    days_since_last_purchase: int | None
    median_purchase_interval_days: Decimal | None
    purchase_interval_mad_days: Decimal | None
    invoice_count_lifetime: int
    invoice_count_90d: int
    sales_30d: Decimal
    sales_90d: Decimal
    outstanding_balance: Decimal
    last_purchase_at: datetime | None
    reason_codes: list[str]


class InactivityGroup(BaseModel):
    currency: str
    items: list[InactivityItem]


class InactivityResponse(BaseModel):
    as_of: datetime
    groups: list[InactivityGroup]


class AnomalyBaseline(BaseModel):
    method: str
    median: Decimal | None
    mad: Decimal | None
    sample_size: int | None


class AnomalyItem(BaseModel):
    type: str
    severity: str
    detected_at: datetime
    subject_type: str
    subject_id: UUID | None
    metric: str
    observed_value: Decimal
    baseline: AnomalyBaseline
    reason_code: str
    details: dict[str, Scalar]


class AnomalyGroup(BaseModel):
    currency: str
    items: list[AnomalyItem]
    insufficient_history: list[str]


class AnomalyWindow(BaseModel):
    start: datetime
    end: datetime
    timezone: str
    block_days: int
    baseline_blocks: int


class AnomaliesResponse(BaseModel):
    as_of: datetime
    window: AnomalyWindow
    groups: list[AnomalyGroup]


class CashPosition(BaseModel):
    customer_receivables: Decimal
    customer_credit: Decimal
    overdue_receivables: Decimal
    overdue_customer_count: int
    supplier_payables: Decimal
    supplier_credit: Decimal


class AgeingBucket(BaseModel):
    bucket: str
    amount: Decimal
    customer_count: int


class HistoricalFlow(BaseModel):
    """What already happened in the period — history, not a prediction."""

    customer_receipts: Decimal
    customer_refunds: Decimal
    supplier_payments: Decimal
    net_customer_collections: Decimal
    average_weekly_collections: Decimal | None


class PlannedCollections(BaseModel):
    """Open delivery tasks' `amount_to_collect` — a projection that ignores invoice adjustments."""

    amount: Decimal
    task_count: int
    from_date: date
    through_date: date
    source: str
    projection_warning_code: str


class CurrencyCashFlow(BaseModel):
    currency: str
    position: CashPosition
    ageing: list[AgeingBucket]
    historical_flow: HistoricalFlow
    planned_collections: PlannedCollections


class CashFlowResponse(BaseModel):
    as_of: datetime
    period: PeriodInfo
    overdue_threshold_days: int | None
    currencies: list[CurrencyCashFlow]


class CopilotMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CopilotQueryRequest(BaseModel):
    """One question plus the client-held, bounded history (never stored on the server). The
    history should carry each earlier answer's `conversation_text` (references, not names)."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1000)
    conversation: list[CopilotMessage] = Field(default_factory=list, max_length=12)
    # Echo the previous response's id to continue a conversation; omit it to start a new one
    # (every customer then gets a fresh reference).
    conversation_id: UUID | None = None


class CopilotReference(BaseModel):
    ref: str
    customer_id: UUID
    customer_name: str


class CopilotGrounding(BaseModel):
    tool: str
    period: str | None
    currency: str | None
    ok: bool


class CopilotResponse(BaseModel):
    conversation_id: UUID
    answer: str
    conversation_text: str
    references: list[CopilotReference]
    grounding: list[CopilotGrounding]
    warnings: list[str]
    unverified_numbers: list[str]


class _ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "ar"] = "en"


class CustomerExplainRequest(_ExplainRequest):
    """A brief about one customer of the owner's business (another tenant's id is not found)."""

    kind: Literal["customer"]
    customer_id: UUID


class AnomalyExplainRequest(_ExplainRequest):
    """One unusual change as the client shows it: its position in the currency's list plus its
    type and subject, re-checked on the server (anomalies are computed, they have no id)."""

    kind: Literal["anomaly"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    index: int = Field(ge=0, le=500)
    type: Literal[
        "SALES_PERIOD_HIGH",
        "SALES_PERIOD_LOW",
        "CANCELLATION_SPIKE",
        "REVERSAL_SPIKE",
        "REFUND_SPIKE",
        "CUSTOMER_INVOICE_VALUE_HIGH",
        "BACKDATED_RECEIPT_LARGE",
        "OVERDUE_THRESHOLD_CROSSED",
        "SUPPLIER_PAYABLE_JUMP",
        "LINE_PRICE_BELOW_SNAPSHOT_COST",
    ]
    subject_id: UUID | None = None


class CashExplainRequest(_ExplainRequest):
    """The cash position for the period (and currency) the Analytics screen shows."""

    kind: Literal["cash"]
    period: Literal["30d", "90d", "1y", "all"] = "90d"
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


ExplainRequest = Annotated[
    CustomerExplainRequest | AnomalyExplainRequest | CashExplainRequest,
    Field(discriminator="kind"),
]


class ExplanationResponse(BaseModel):
    kind: str
    as_of: datetime
    answer: str
    references: list[CopilotReference]
    grounding: list[CopilotGrounding]
    warnings: list[str]
    unverified_numbers: list[str]


class CopilotStatus(BaseModel):
    configured: bool
    provider: str | None
    model: str | None
