from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SnapshotCollection = Literal[
    "customers",
    "categories",
    "tenant_products",
    "tenant_barcodes",
    "invoices",
    "invoice_revisions",
    "invoice_revision_items",
    "payments",
    "customer_ledger_entries",
]


class BootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_installation_id: UUID
    protocol_version: int = Field(ge=1)
    app_schema_version: int = Field(ge=1)


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    device_installation_id: UUID
    protocol_version: int
    app_schema_version: int
    last_acknowledged_change_seq: int
    lease_expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None


class BootstrapResponse(BaseModel):
    device: DeviceResponse
    high_water_change_seq: int
    protocol_version: int
    app_schema_version: int
    collections: list[str]
    page_size: int


class SnapshotPageResponse(BaseModel):
    collection: str
    items: list[dict[str, Any]]
    next_cursor: str | None
    high_water_change_seq: int


class PushOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    entity_type: Literal[
        "customer",
        "category",
        "tenant_product",
        "invoice",
        "payment",
        # Phase 6 (PHASE_06.md I): supplier profile, price append, procurement line edit and the
        # financial supplier purchase / payment commands ride the same protocol.
        "supplier",
        "product_cost",
        "procurement_item",
        "supplier_purchase",
        "supplier_payment",
        # Phase 7 (PHASE_07.md I): completion of an assigned delivery task.
        "delivery_task",
    ]
    operation_type: Literal[
        "create",
        "update",
        "archive",
        "confirm",
        "cancel",
        "receipt",
        "refund",
        "reverse",
        "complete",
    ]
    entity_id: UUID
    expected_version: int | None = Field(default=None, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    client_timestamp: datetime


class PushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_installation_id: UUID
    protocol_version: int = Field(ge=1)
    operations: list[PushOperation] = Field(min_length=1, max_length=200)


class ConflictEnvelope(BaseModel):
    entity_type: str
    entity_id: UUID
    server_version: int
    client_expected_version: int | None
    operation_id: UUID
    merge_strategy: Literal["manual"] = "manual"
    server_projection: dict[str, Any] | None
    request_id: UUID


class PushError(BaseModel):
    code: str
    message: str


class PushResult(BaseModel):
    operation_id: UUID
    status: Literal["applied", "rejected", "conflict"]
    replayed: bool = False
    entity_type: str
    entity_id: UUID
    version: int | None = None
    projection: dict[str, Any] | None = None
    error: PushError | None = None
    conflict: ConflictEnvelope | None = None


class PushResponse(BaseModel):
    results: list[PushResult]
    high_water_change_seq: int


class ChangeRecord(BaseModel):
    change_seq: int
    entity_type: str
    entity_id: UUID
    operation: Literal["upsert", "delete"]
    version: int
    payload: dict[str, Any]
    operation_id: UUID | None
    device_installation_id: UUID | None
    occurred_at: datetime


class PullResponse(BaseModel):
    changes: list[ChangeRecord]
    next_cursor: int
    high_water_change_seq: int
    has_more: bool
    protocol_version: int
