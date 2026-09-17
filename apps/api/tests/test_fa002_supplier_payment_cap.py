"""FA-002 regression: ordinary supplier payments are payable-capped; excess needs an explicit
prepayment (D-039, FI-23/FI-24)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from test_invoice_editor import _auth
from test_supplier_ledger import _supplier_context

from tawzeevo_api.models import Payment, SupplierLedgerEntry, SupplierLedgerEntryType


def _opening(client, tenant, token, supplier, currency, amount):
    response = client.post(
        f"/api/v1/supplier-ledger/opening-balances?tenant_id={tenant}",
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier,
            "currency": currency,
            "signed_amount": amount,
            "effective_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 201, response.text


def _payment_payload(supplier, currency, amount, key=None):
    return {
        "idempotency_key": key or str(uuid4()),
        "supplier_id": supplier,
        "currency": currency,
        "amount": amount,
        "paid_at": datetime.now(UTC).isoformat(),
        "method": "CASH",
    }


def _balance(client, tenant, token, supplier, currency) -> str:
    response = client.get(
        f"/api/v1/supplier-ledger/{supplier}/balances?tenant_id={tenant}",
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    for row in response.json()["balances"]:
        if row["currency"] == currency:
            return row["balance"]
    return "0.0000"


def test_ordinary_payment_is_capped_and_prepayment_records_labelled_credit(client, session_factory):
    _, tenant, token, supplier = _supplier_context(client, session_factory)
    headers = _auth(token)
    _opening(client, tenant, token, supplier, "USD", "20.0000")
    _opening(client, tenant, token, supplier, "LBP", "500000.0000")

    excess = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
        headers=headers,
        json=_payment_payload(supplier, "USD", "25.0000"),
    )
    assert excess.status_code == 409, excess.text
    assert excess.json()["detail"]["code"] == "SUPPLIER_PAYMENT_EXCEEDS_PAYABLE"
    assert _balance(client, tenant, token, supplier, "USD") == "20.0000"

    exact = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
        headers=headers,
        json=_payment_payload(supplier, "USD", "20.0000"),
    )
    assert exact.status_code == 201, exact.text
    assert exact.json()["prepayment"] is False
    assert _balance(client, tenant, token, supplier, "USD") == "0.0000"

    zero_payable = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
        headers=headers,
        json=_payment_payload(supplier, "USD", "0.0100"),
    )
    assert zero_payable.status_code == 409, zero_payable.text

    # The LBP payable is independent of the exhausted USD payable.
    lbp = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
        headers=headers,
        json=_payment_payload(supplier, "LBP", "100000.0000"),
    )
    assert lbp.status_code == 201, lbp.text
    assert _balance(client, tenant, token, supplier, "LBP") == "400000.0000"

    prepayment_payload = _payment_payload(supplier, "USD", "5.0000")
    prepayment = client.post(
        f"/api/v1/payments/supplier-prepayments?tenant_id={tenant}",
        headers=headers,
        json=prepayment_payload,
    )
    assert prepayment.status_code == 201, prepayment.text
    assert prepayment.json()["prepayment"] is True
    assert _balance(client, tenant, token, supplier, "USD") == "-5.0000"
    replay = client.post(
        f"/api/v1/payments/supplier-prepayments?tenant_id={tenant}",
        headers=headers,
        json=prepayment_payload,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json() == prepayment.json()
    # The same command cannot be replayed as a different action.
    as_ordinary = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
        headers=headers,
        json=prepayment_payload,
    )
    assert as_ordinary.status_code == 409, as_ordinary.text

    with session_factory() as db:
        entry = db.scalar(
            select(SupplierLedgerEntry).where(
                SupplierLedgerEntry.source_effect_key
                == f"supplier-payment:{prepayment.json()['id']}"
            )
        )
        assert entry is not None
        assert entry.entry_type == SupplierLedgerEntryType.SUPPLIER_PREPAYMENT
        assert entry.signed_amount == Decimal("-5.0000")
        assert (
            db.scalar(select(Payment.direction).where(Payment.id == entry.source_id))
            == "SUPPLIER_PAYMENT"
        )

    reversed_prepayment = client.post(
        f"/api/v1/payments/supplier-payments/{prepayment.json()['id']}/reverse?tenant_id={tenant}",
        headers=headers,
        json={"idempotency_key": str(uuid4()), "reason": "Recorded against wrong supplier"},
    )
    assert reversed_prepayment.status_code == 201, reversed_prepayment.text
    assert _balance(client, tenant, token, supplier, "USD") == "0.0000"
    with session_factory() as db:
        assert db.scalar(
            select(SupplierLedgerEntry.signed_amount).where(
                SupplierLedgerEntry.source_effect_key
                == f"supplier-payment:{reversed_prepayment.json()['id']}"
            )
        ) == Decimal("5.0000")


def test_concurrent_ordinary_payments_cannot_exceed_payable(client, session_factory):
    _, tenant, token, supplier = _supplier_context(client, session_factory)
    _opening(client, tenant, token, supplier, "USD", "20.0000")

    def pay():
        return client.post(
            f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
            headers=_auth(token),
            json=_payment_payload(supplier, "USD", "15.0000"),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: pay(), range(2)))
    assert statuses == [201, 409], statuses
    assert _balance(client, tenant, token, supplier, "USD") == "5.0000"
