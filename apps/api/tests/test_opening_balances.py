from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_invoice_editor import _auth, _catalog, _owner_context

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    CustomerLedgerEntry,
    LedgerEntryType,
    SupplierLedgerEntry,
    SupplierLedgerEntryType,
    TenantSupplier,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.customer_ledger import OpeningBalanceRequest
from tawzeevo_api.schemas.supplier_ledger import SupplierOpeningRequest
from tawzeevo_api.services.customer_ledger import create_opening_balance
from tawzeevo_api.services.supplier_ledger import record_supplier_opening


def _supplier(session_factory, tenant_id: str, name: str = "Opening supplier") -> str:
    with session_factory() as db:
        supplier = TenantSupplier(tenant_id=tenant_id, name=name)
        db.add(supplier)
        db.commit()
        return str(supplier.id)


def test_customer_opening_is_once_per_currency_signed_and_correctable(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "customer-opening-invariant")
    _, _, customer = _catalog(client, tenant, token)
    path = "/api/v1/customer-ledger/opening-balances"
    now = datetime.now(UTC).isoformat()
    opening = {
        "idempotency_key": str(uuid4()),
        "customer_id": customer["id"],
        "currency": "USD",
        "signed_amount": "10.0000",
        "effective_at": now,
        "note": "Initial historical debt",
    }
    created = client.post(path, params={"tenant_id": tenant}, headers=_auth(token), json=opening)
    assert created.status_code == 201, created.text

    duplicate = client.post(
        path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={**opening, "idempotency_key": str(uuid4()), "signed_amount": "12.0000"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "OPENING_BALANCE_ALREADY_EXISTS"

    credit = client.post(
        path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={
            **opening,
            "idempotency_key": str(uuid4()),
            "currency": "LBP",
            "signed_amount": "-500000.0000",
            "note": "Pre-existing historical credit",
        },
    )
    assert credit.status_code == 201, credit.text
    zero = client.post(
        path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={**opening, "idempotency_key": str(uuid4()), "currency": "EUR", "signed_amount": "0"},
    )
    assert zero.status_code == 422

    reversal_payload = {
        "idempotency_key": str(uuid4()),
        "corrected_signed_amount": "12.0000",
        "reason": "Correct historical source document",
    }
    reverse_path = f"{path}/{created.json()['id']}/correct"
    reversed_entry = client.post(
        reverse_path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json=reversal_payload,
    )
    assert reversed_entry.status_code == 201, reversed_entry.text
    assert reversed_entry.json()["entry_type"] == "OPENING_BALANCE_CORRECTION"
    assert reversed_entry.json()["signed_amount"] == "2.0000"
    assert reversed_entry.json()["reverses_entry_id"] == created.json()["id"]
    assert (
        client.post(
            reverse_path,
            params={"tenant_id": tenant},
            headers=_auth(token),
            json=reversal_payload,
        ).json()
        == reversed_entry.json()
    )
    second_reversal = client.post(
        reverse_path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "corrected_signed_amount": "15.0000",
            "reason": "Another correction",
        },
    )
    assert second_reversal.status_code == 409

    balances = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant},
        headers=_auth(token),
    )
    assert balances.status_code == 200
    assert {row["currency"]: row["balance"] for row in balances.json()["balances"]} == {
        "LBP": "-500000.0000",
        "USD": "12.0000",
    }
    with session_factory() as db:
        original = db.get(CustomerLedgerEntry, UUID(created.json()["id"]))
        assert original is not None
        assert original.entry_type == LedgerEntryType.OPENING_BALANCE
        assert original.signed_amount == Decimal("10.0000")
        assert original.metadata_json == {
            "note": "Initial historical debt",
            "opening_classification": "HISTORICAL_DEBT",
        }
        historical_credit = db.get(CustomerLedgerEntry, UUID(credit.json()["id"]))
        assert historical_credit is not None
        assert historical_credit.metadata_json["opening_classification"] == "HISTORICAL_CREDIT"
        correction = db.get(CustomerLedgerEntry, UUID(reversed_entry.json()["id"]))
        assert correction is not None
        assert correction.metadata_json["corrected_opening_classification"] == "HISTORICAL_DEBT"
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant,
                AuditEvent.action == "customer_opening_balance_corrected",
                AuditEvent.entity_id == correction.id,
            )
        )
        assert audit is not None
        assert audit.details["original_opening_entry_id"] == created.json()["id"]
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                CustomerLedgerEntry(
                    tenant_id=tenant,
                    customer_id=customer["id"],
                    currency="USD",
                    signed_amount=Decimal("99.0000"),
                    entry_type=LedgerEntryType.OPENING_BALANCE,
                    source_type="OPENING_BALANCE",
                    source_effect_key=f"direct-duplicate:{uuid4()}",
                    effective_at=datetime.now(UTC),
                    idempotency_key=uuid4(),
                )
            )
            db.flush()


def test_supplier_opening_is_once_per_currency_signed_and_correctable(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "supplier-opening-invariant")
    supplier_id = _supplier(session_factory, tenant)
    path = "/api/v1/supplier-ledger/opening-balances"
    now = datetime.now(UTC).isoformat()
    opening = {
        "idempotency_key": str(uuid4()),
        "supplier_id": supplier_id,
        "currency": "USD",
        "signed_amount": "20.0000",
        "effective_at": now,
        "note": "Initial supplier payable",
    }
    created = client.post(path, params={"tenant_id": tenant}, headers=_auth(token), json=opening)
    assert created.status_code == 201, created.text
    duplicate = client.post(
        path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={**opening, "idempotency_key": str(uuid4()), "signed_amount": "30.0000"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "OPENING_BALANCE_ALREADY_EXISTS"
    credit = client.post(
        path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={
            **opening,
            "idempotency_key": str(uuid4()),
            "currency": "LBP",
            "signed_amount": "-250000.0000",
            "note": "Pre-existing historical credit",
        },
    )
    assert credit.status_code == 201, credit.text
    zero = client.post(
        path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={**opening, "idempotency_key": str(uuid4()), "currency": "EUR", "signed_amount": "0"},
    )
    assert zero.status_code == 422

    with session_factory() as db:
        original = db.scalar(
            select(SupplierLedgerEntry).where(
                SupplierLedgerEntry.tenant_id == tenant,
                SupplierLedgerEntry.supplier_id == supplier_id,
                SupplierLedgerEntry.currency == "USD",
                SupplierLedgerEntry.entry_type == SupplierLedgerEntryType.OPENING_BALANCE,
            )
        )
        assert original is not None
        original_id = str(original.id)
    reversal_payload = {
        "idempotency_key": str(uuid4()),
        "corrected_signed_amount": "0.0000",
        "reason": "Opening entered in error",
    }
    reverse_path = f"{path}/{original_id}/correct"
    reversed_entry = client.post(
        reverse_path,
        params={"tenant_id": tenant},
        headers=_auth(token),
        json=reversal_payload,
    )
    assert reversed_entry.status_code == 201, reversed_entry.text
    assert reversed_entry.json()["entry_type"] == "OPENING_BALANCE_CORRECTION"
    assert reversed_entry.json()["signed_amount"] == "-20.0000"
    assert reversed_entry.json()["reverses_entry_id"] == original_id
    assert (
        client.post(
            reverse_path,
            params={"tenant_id": tenant},
            headers=_auth(token),
            json=reversal_payload,
        ).json()
        == reversed_entry.json()
    )
    assert (
        client.post(
            reverse_path,
            params={"tenant_id": tenant},
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "corrected_signed_amount": "5.0000",
                "reason": "Another correction",
            },
        ).status_code
        == 409
    )
    balances = client.get(
        f"/api/v1/supplier-ledger/{supplier_id}/balances",
        params={"tenant_id": tenant},
        headers=_auth(token),
    )
    assert {row["currency"]: row["balance"] for row in balances.json()["balances"]} == {
        "LBP": "-250000.0000",
        "USD": "0.0000",
    }
    with session_factory() as db:
        original = db.get(SupplierLedgerEntry, UUID(original_id))
        assert original is not None
        assert original.entry_type == SupplierLedgerEntryType.OPENING_BALANCE
        assert original.signed_amount == Decimal("20.0000")
        assert original.metadata_json == {
            "note": "Initial supplier payable",
            "opening_classification": "HISTORICAL_PAYABLE",
        }
        correction = db.get(SupplierLedgerEntry, UUID(reversed_entry.json()["id"]))
        assert correction is not None
        assert correction.metadata_json["corrected_opening_classification"] == "REVERSED"
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant,
                AuditEvent.action == "supplier_opening_balance_corrected",
                AuditEvent.entity_id == correction.id,
            )
        )
        assert audit is not None
        assert audit.details["original_opening_entry_id"] == original_id
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                SupplierLedgerEntry(
                    tenant_id=tenant,
                    supplier_id=supplier_id,
                    currency="USD",
                    signed_amount=Decimal("99.0000"),
                    entry_type=SupplierLedgerEntryType.OPENING_BALANCE,
                    source_type="OPENING_BALANCE",
                    source_effect_key=f"direct-duplicate:{uuid4()}",
                    effective_at=datetime.now(UTC),
                    idempotency_key=uuid4(),
                )
            )
            db.flush()


def test_concurrent_customer_and_supplier_duplicate_openings_are_serialized(
    client, session_factory
):
    owner, tenant, token = _owner_context(client, session_factory, "opening-concurrency")
    _, _, customer = _catalog(client, tenant, token)
    supplier_id = _supplier(session_factory, tenant)
    effective_at = datetime.now(UTC)

    def customer_attempt(_: int) -> int:
        with session_factory() as db:
            set_tenant_scope(db, UUID(tenant))
            try:
                create_opening_balance(
                    db,
                    UUID(tenant),
                    owner.id,
                    OpeningBalanceRequest(
                        idempotency_key=uuid4(),
                        customer_id=UUID(customer["id"]),
                        currency="USD",
                        signed_amount=Decimal("10.0000"),
                        effective_at=effective_at,
                    ),
                )
            except AppError as error:
                db.rollback()
                return error.status_code
            return 201

    def supplier_attempt(_: int) -> int:
        with session_factory() as db:
            set_tenant_scope(db, UUID(tenant))
            try:
                record_supplier_opening(
                    db,
                    UUID(tenant),
                    owner.id,
                    SupplierOpeningRequest(
                        idempotency_key=uuid4(),
                        supplier_id=UUID(supplier_id),
                        currency="USD",
                        signed_amount=Decimal("20.0000"),
                        effective_at=effective_at,
                    ),
                )
            except AppError as error:
                db.rollback()
                return error.status_code
            return 201

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(customer_attempt, range(2))) == [201, 409]
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(supplier_attempt, range(2))) == [201, 409]
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CustomerLedgerEntry)
                .where(CustomerLedgerEntry.entry_type == LedgerEntryType.OPENING_BALANCE)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierLedgerEntry)
                .where(SupplierLedgerEntry.entry_type == SupplierLedgerEntryType.OPENING_BALANCE)
            )
            == 1
        )


def test_opening_uniqueness_is_tenant_scoped(client, session_factory):
    for suffix in ("opening-tenant-one", "opening-tenant-two"):
        _, tenant, token = _owner_context(client, session_factory, suffix)
        _, _, customer = _catalog(client, tenant, token, barcode=f"5280{uuid4().int % 10**9:09d}")
        supplier_id = _supplier(session_factory, tenant, f"Supplier {suffix}")
        customer_response = client.post(
            "/api/v1/customer-ledger/opening-balances",
            params={"tenant_id": tenant},
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "customer_id": customer["id"],
                "currency": "USD",
                "signed_amount": "1.0000",
                "effective_at": datetime.now(UTC).isoformat(),
            },
        )
        supplier_response = client.post(
            "/api/v1/supplier-ledger/opening-balances",
            params={"tenant_id": tenant},
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "supplier_id": supplier_id,
                "currency": "USD",
                "signed_amount": "1.0000",
                "effective_at": datetime.now(UTC).isoformat(),
            },
        )
        assert customer_response.status_code == supplier_response.status_code == 201
