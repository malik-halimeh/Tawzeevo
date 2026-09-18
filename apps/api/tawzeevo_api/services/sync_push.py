"""Idempotent sync push (PHASE_04.md F/H; D-045 style command identity).

Each queued device operation is applied in its own PostgreSQL transaction together with its
idempotency record and the change-log rows produced by the flush listener. Replaying an operation
returns the stored result; a different request under the same operation id is rejected; a stale
`expected_version` produces a conflict envelope and never overwrites the server row.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    Category,
    Customer,
    SyncOperation,
    TenantMembership,
    TenantProduct,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.cash_van import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
    CustomerCreateRequest,
    CustomerUpdateRequest,
    TenantProductCreateRequest,
    TenantProductUpdateRequest,
)
from tawzeevo_api.schemas.invoice_editor import InvoiceCancelRequest, InvoiceEditorDraftRequest
from tawzeevo_api.schemas.payments import (
    CustomerReceiptRequest,
    CustomerRefundRequest,
    PaymentReversalRequest,
)
from tawzeevo_api.schemas.sync import (
    ConflictEnvelope,
    PushError,
    PushOperation,
    PushRequest,
    PushResponse,
    PushResult,
)
from tawzeevo_api.services import sync_changes
from tawzeevo_api.services.cash_van import build_product, get_category, get_customer, get_product
from tawzeevo_api.services.invoice_editor import create_editor_draft, update_editor_draft
from tawzeevo_api.services.invoice_finance import (
    cancel_invoice,
    confirm_invoice,
    update_confirmed_invoice,
)
from tawzeevo_api.services.payments import (
    record_customer_receipt,
    record_customer_refund,
    reverse_customer_receipt,
)
from tawzeevo_api.services.pricing import list_product_grade_prices
from tawzeevo_api.services.sync import active_device, high_water
from tawzeevo_api.services.sync_changes import PROJECTIONS, PROTOCOL_VERSION


def _fingerprint(operation: PushOperation) -> str:
    canonical = json.dumps(
        {
            "entity_type": operation.entity_type,
            "operation_type": operation.operation_type,
            "entity_id": str(operation.entity_id),
            "expected_version": operation.expected_version,
            "payload": operation.payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _lock(db: Session, operation_id: UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": operation_id.int & ((1 << 63) - 1)},
    )


def _projection(row: Any) -> dict[str, Any]:
    return PROJECTIONS[type(row)][1](row)


class _Conflict(Exception):
    def __init__(self, row: Any, expected: int | None) -> None:
        self.row = row
        self.expected = expected


def _check_version(row: Any, operation: PushOperation) -> None:
    if operation.expected_version is None:
        raise AppError(400, "EXPECTED_VERSION_REQUIRED", "Updates must carry expected_version")
    if int(row.version) != operation.expected_version:
        raise _Conflict(row, operation.expected_version)


def _apply_customer(db: Session, tenant_id: UUID, operation: PushOperation) -> Any:
    if operation.operation_type == "create":
        create = CustomerCreateRequest.model_validate(operation.payload)
        existing = db.get(Customer, operation.entity_id)
        if existing is not None:
            raise AppError(409, "ENTITY_ID_IN_USE", "Entity id already exists")
        try:
            phone = normalize_phone(create.phone)
        except InvalidPhoneNumberError as exc:
            raise AppError(422, "INVALID_PHONE", "Customer phone is invalid") from exc
        row = Customer(
            id=operation.entity_id,
            tenant_id=tenant_id,
            name=create.name,
            phone=phone,
            phone_raw=create.phone,
            address=create.address,
            latitude=create.latitude,
            longitude=create.longitude,
            grade=create.grade,
        )
        db.add(row)
        db.flush()
        return row
    if operation.operation_type == "update":
        row = get_customer(db, tenant_id, operation.entity_id)
        _check_version(row, operation)
        update = CustomerUpdateRequest.model_validate(operation.payload)
        values = update.model_dump(exclude_unset=True)
        if "phone" in values:
            try:
                row.phone = normalize_phone(values["phone"])
            except InvalidPhoneNumberError as exc:
                raise AppError(422, "INVALID_PHONE", "Customer phone is invalid") from exc
            row.phone_raw = values.pop("phone")
        for field_name, value in values.items():
            setattr(row, field_name, value)
        db.flush()
        return row
    raise AppError(400, "UNSUPPORTED_OPERATION", "Customers cannot be archived")


def _apply_category(db: Session, tenant_id: UUID, operation: PushOperation) -> Any:
    if operation.operation_type == "create":
        create = CategoryCreateRequest.model_validate(operation.payload)
        if db.get(Category, operation.entity_id) is not None:
            raise AppError(409, "ENTITY_ID_IN_USE", "Entity id already exists")
        duplicate = db.scalar(
            select(Category.id).where(Category.tenant_id == tenant_id, Category.slug == create.slug)
        )
        if duplicate is not None:
            raise AppError(409, "CATEGORY_SLUG_ALREADY_EXISTS", "Category slug already exists")
        row = Category(
            id=operation.entity_id,
            tenant_id=tenant_id,
            master_category_id=create.master_category_id,
            name_en=create.name_en,
            name_ar=create.name_ar,
            slug=create.slug,
            display_order=create.display_order,
        )
        db.add(row)
        db.flush()
        return row
    row = get_category(db, tenant_id, operation.entity_id)
    _check_version(row, operation)
    if operation.operation_type == "archive":
        if row.is_active:
            row.is_active = False
            row.archived_at = datetime.now(UTC)
            db.flush()
        return row
    if not row.is_active:
        raise AppError(409, "CATEGORY_ARCHIVED", "Archived categories cannot be changed")
    update = CategoryUpdateRequest.model_validate(operation.payload)
    values = update.model_dump(exclude_unset=True)
    if "slug" in values and values["slug"] != row.slug:
        duplicate = db.scalar(
            select(Category.id).where(
                Category.tenant_id == tenant_id, Category.slug == values["slug"]
            )
        )
        if duplicate is not None:
            raise AppError(409, "CATEGORY_SLUG_ALREADY_EXISTS", "Category slug already exists")
    for field_name, value in values.items():
        setattr(row, field_name, value)
    db.flush()
    return row


def _apply_product(db: Session, tenant_id: UUID, operation: PushOperation) -> Any:
    if operation.operation_type == "create":
        create = TenantProductCreateRequest.model_validate(operation.payload)
        if db.get(TenantProduct, operation.entity_id) is not None:
            raise AppError(409, "ENTITY_ID_IN_USE", "Entity id already exists")
        return build_product(db, tenant_id, create, product_id=operation.entity_id)
    if operation.operation_type == "update":
        row = get_product(db, tenant_id, operation.entity_id)
        _check_version(row, operation)
        update = TenantProductUpdateRequest.model_validate(operation.payload)
        values = update.model_dump(exclude_unset=True)
        if "category_id" in values:
            get_category(db, tenant_id, values["category_id"], active_only=True)
        if list_product_grade_prices(db, tenant_id, row.id) and (
            ("price_basis" in values and values["price_basis"] != row.price_basis)
            or ("currency" in values and values["currency"] != row.currency)
        ):
            raise AppError(
                409,
                "GRADE_PRICES_BASIS_LOCKED",
                "Clear explicit grade prices before changing currency or basis",
            )
        for field_name, value in values.items():
            setattr(row, field_name, value)
        db.flush()
        return row
    raise AppError(400, "UNSUPPORTED_OPERATION", "Products cannot be archived")


_APPLIERS: dict[str, Callable[[Session, UUID, PushOperation], Any]] = {
    "customer": _apply_customer,
    "category": _apply_category,
    "tenant_product": _apply_product,
}


# ---------------------------------------------------------------------------------------------
# Financial commands (PHASE_04.md D/I). These reuse the Phase 3 services unchanged: the same
# idempotency keys, ledger effects and server-only official numbering apply. The services commit
# themselves, so the idempotency record is staged BEFORE the call and completed afterwards; the
# financial services' own replay protection keeps a crash between the two commits harmless.
# ---------------------------------------------------------------------------------------------

FINANCIAL_TYPES = {"invoice", "payment"}


def _financial_payload(operation: PushOperation) -> dict[str, Any]:
    payload = dict(operation.payload)
    # The device's operation id is the financial command identity when it did not send one.
    if operation.entity_type == "invoice" and operation.operation_type in {"create", "update"}:
        payload.setdefault("client_command_id", str(operation.operation_id))
    if operation.entity_type == "invoice" and operation.operation_type == "cancel":
        payload.setdefault("idempotency_key", str(operation.operation_id))
    if operation.entity_type == "payment":
        payload.setdefault("idempotency_key", str(operation.operation_id))
    payload.pop("confirmed", None)
    return payload


def _apply_financial(
    db: Session, tenant_id: UUID, actor: UUID, operation: PushOperation
) -> dict[str, Any]:
    payload = _financial_payload(operation)
    threshold = get_settings().invoice_fuzzy_match_threshold
    kind = (operation.entity_type, operation.operation_type)
    response: Any
    if kind == ("invoice", "create"):
        request = InvoiceEditorDraftRequest.model_validate(payload)
        response = create_editor_draft(db, tenant_id, actor, request, fuzzy_threshold=threshold)
    elif kind == ("invoice", "update"):
        request = InvoiceEditorDraftRequest.model_validate(payload)
        if operation.payload.get("confirmed"):
            response = update_confirmed_invoice(
                db, tenant_id, actor, operation.entity_id, request, fuzzy_threshold=threshold
            )
        else:
            response = update_editor_draft(
                db, tenant_id, actor, operation.entity_id, request, fuzzy_threshold=threshold
            )
    elif kind == ("invoice", "confirm"):
        expected = payload.get("expected_revision_id")
        if not expected:
            raise AppError(400, "EXPECTED_REVISION_REQUIRED", "Confirmation needs the revision")
        response = confirm_invoice(db, tenant_id, actor, operation.entity_id, UUID(str(expected)))
    elif kind == ("invoice", "cancel"):
        response = cancel_invoice(
            db, tenant_id, actor, operation.entity_id, InvoiceCancelRequest.model_validate(payload)
        )
    elif kind == ("payment", "receipt"):
        response = record_customer_receipt(
            db, tenant_id, actor, CustomerReceiptRequest.model_validate(payload)
        )
    elif kind == ("payment", "refund"):
        response = record_customer_refund(
            db, tenant_id, actor, CustomerRefundRequest.model_validate(payload)
        )
    elif kind == ("payment", "reverse"):
        response = reverse_customer_receipt(
            db,
            tenant_id,
            actor,
            operation.entity_id,
            PaymentReversalRequest.model_validate(payload),
        )
    else:
        raise AppError(400, "UNSUPPORTED_OPERATION", "Unsupported financial operation")
    projection: dict[str, Any] = json.loads(response.model_dump_json())
    return projection


def _apply_financial_op(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    request: PushRequest,
    operation: PushOperation,
    staged: SyncOperation | None = None,
) -> PushResult:
    fingerprint = _fingerprint(operation)
    if staged is None:
        staged = SyncOperation(
            tenant_id=tenant_id,
            device_installation_id=request.device_installation_id,
            operation_id=operation.operation_id,
            entity_type=operation.entity_type,
            operation_type=operation.operation_type,
            status="applied",
            result={},
            request_fingerprint=fingerprint,
        )
        db.add(staged)
        db.flush()
    staged_id = staged.id
    sync_changes.set_operation_context(db, operation.operation_id, request.device_installation_id)
    try:
        try:
            projection = _apply_financial(db, tenant_id, actor, operation)
        except ValidationError as exc:
            raise AppError(422, "VALIDATION_ERROR", exc.errors()[0].get("msg", "invalid")) from exc
        result = PushResult(
            operation_id=operation.operation_id,
            status="applied",
            entity_type=operation.entity_type,
            entity_id=UUID(str(projection.get("id", operation.entity_id))),
            version=None,
            projection=projection,
        )
        record = db.get(SyncOperation, staged_id)
        if record is not None:
            record.result = json.loads(result.model_dump_json())
        commit_and_restore_tenant_scope(db, tenant_id)
        return result
    except AppError as error:
        db.rollback()
        result = PushResult(
            operation_id=operation.operation_id,
            status="rejected",
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            error=PushError(code=error.code, message=error.message),
        )
        _lock(db, operation.operation_id)
        committed = db.get(SyncOperation, staged_id)
        if committed is not None:  # staged row survived an earlier commit: complete it
            committed.status = "rejected"
            committed.result = json.loads(result.model_dump_json())
        else:
            _record(db, tenant_id, request, operation, result, fingerprint)
        commit_and_restore_tenant_scope(db, tenant_id)
        return result
    finally:
        sync_changes.set_operation_context(db, None, None)


def _stored_result(record: SyncOperation) -> PushResult:
    return PushResult.model_validate({**record.result, "replayed": True})


def _record(
    db: Session,
    tenant_id: UUID,
    request: PushRequest,
    operation: PushOperation,
    result: PushResult,
    fingerprint: str,
) -> None:
    db.add(
        SyncOperation(
            tenant_id=tenant_id,
            device_installation_id=request.device_installation_id,
            operation_id=operation.operation_id,
            entity_type=operation.entity_type,
            operation_type=operation.operation_type,
            status=result.status,
            result=json.loads(result.model_dump_json()),
            request_fingerprint=fingerprint,
        )
    )


def _apply_one(
    db: Session, tenant_id: UUID, actor: UUID, request: PushRequest, operation: PushOperation
) -> PushResult:
    _lock(db, operation.operation_id)
    fingerprint = _fingerprint(operation)
    existing = db.scalar(
        select(SyncOperation).where(
            SyncOperation.tenant_id == tenant_id,
            SyncOperation.device_installation_id == request.device_installation_id,
            SyncOperation.operation_id == operation.operation_id,
        )
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            db.rollback()
            return PushResult(
                operation_id=operation.operation_id,
                status="rejected",
                entity_type=operation.entity_type,
                entity_id=operation.entity_id,
                error=PushError(
                    code="IDEMPOTENCY_CONFLICT",
                    message="This operation id was already used for a different request",
                ),
            )
        if existing.entity_type in FINANCIAL_TYPES and not existing.result:
            # The financial service committed but the process died before the result was
            # stored. Re-running is safe: the service replays its own idempotency key and the
            # same effect is returned, this time recorded.
            return _apply_financial_op(db, tenant_id, actor, request, operation, existing)
        db.rollback()
        return _stored_result(existing)

    if operation.entity_type in FINANCIAL_TYPES:
        return _apply_financial_op(db, tenant_id, actor, request, operation)
    sync_changes.set_operation_context(db, operation.operation_id, request.device_installation_id)
    try:
        try:
            row = _APPLIERS[operation.entity_type](db, tenant_id, operation)
        except ValidationError as exc:
            raise AppError(422, "VALIDATION_ERROR", exc.errors()[0].get("msg", "invalid")) from exc
        result = PushResult(
            operation_id=operation.operation_id,
            status="applied",
            entity_type=operation.entity_type,
            entity_id=row.id,
            version=int(getattr(row, "version", 1)),
            projection=_projection(row),
        )
        _record(db, tenant_id, request, operation, result, fingerprint)
        commit_and_restore_tenant_scope(db, tenant_id)
        return result
    except _Conflict as conflict:
        db.rollback()
        result = PushResult(
            operation_id=operation.operation_id,
            status="conflict",
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            version=int(conflict.row.version),
            conflict=ConflictEnvelope(
                entity_type=operation.entity_type,
                entity_id=operation.entity_id,
                server_version=int(conflict.row.version),
                client_expected_version=conflict.expected,
                operation_id=operation.operation_id,
                server_projection=_projection(conflict.row),
                request_id=uuid4(),
            ),
        )
        # Conflicts are recorded so a replay returns the same envelope without re-evaluating.
        _lock(db, operation.operation_id)
        _record(db, tenant_id, request, operation, result, fingerprint)
        commit_and_restore_tenant_scope(db, tenant_id)
        return result
    except AppError as error:
        db.rollback()
        result = PushResult(
            operation_id=operation.operation_id,
            status="rejected",
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            error=PushError(code=error.code, message=error.message),
        )
        _lock(db, operation.operation_id)
        _record(db, tenant_id, request, operation, result, fingerprint)
        commit_and_restore_tenant_scope(db, tenant_id)
        return result
    finally:
        sync_changes.set_operation_context(db, None, None)


def push_operations(
    db: Session, tenant_id: UUID, membership: TenantMembership, request: PushRequest
) -> PushResponse:
    if request.protocol_version != PROTOCOL_VERSION:
        raise AppError(409, "SYNC_PROTOCOL_MISMATCH", "Unsupported sync protocol version")
    active_device(db, tenant_id, membership, request.device_installation_id)
    commit_and_restore_tenant_scope(db, tenant_id)
    results = [
        _apply_one(db, tenant_id, membership.user_id, request, operation)
        for operation in request.operations
    ]
    return PushResponse(results=results, high_water_change_seq=high_water(db, tenant_id))
