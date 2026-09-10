from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)

from tawzeevo_api.models import CustomerLedgerEntry, LedgerEntryType


def _opening(
    client,
    tenant_id: str,
    token: str,
    customer_id: str,
    signed_amount: str,
    *,
    currency: str = "USD",
    effective_at: datetime | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/customer-ledger/opening-balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer_id,
            "currency": currency,
            "signed_amount": signed_amount,
            "effective_at": (effective_at or datetime.now(UTC)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _correct(
    client,
    tenant_id: str,
    token: str,
    opening_id: object,
    corrected_signed_amount: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/customer-ledger/opening-balances/{opening_id}/correct",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "corrected_signed_amount": corrected_signed_amount,
            "reason": "FA-008 obligation regression",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _obligations(
    client, tenant_id: str, token: str, customer_id: object, currency: str = "USD"
) -> list[dict[str, object]]:
    response = client.get(
        f"/api/v1/payments/customers/{customer_id}/obligations",
        params={"tenant_id": tenant_id, "currency": currency},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["obligations"]


@pytest.mark.parametrize(
    ("opening_amount", "corrected_amount", "expected_obligation"),
    [
        ("10.0000", None, "10.0000"),
        ("-10.0000", None, None),
        ("10.0000", "12.0000", "12.0000"),
        ("20.0000", "0.0000", None),
        ("-10.0000", "-5.0000", None),
        ("-10.0000", "5.0000", "5.0000"),
    ],
    ids=[
        "positive-opening",
        "negative-opening",
        "positive-corrected-up",
        "positive-reversed-to-zero",
        "negative-remains-credit",
        "credit-crosses-into-debt",
    ],
)
def test_opening_obligation_uses_combined_signed_economic_position(
    client,
    session_factory,
    opening_amount: str,
    corrected_amount: str | None,
    expected_obligation: str | None,
) -> None:
    suffix = f"fa008-position-{uuid4().hex}"
    _owner, tenant_id, token = _owner_context(client, session_factory, suffix)
    _category, _product, customer = _catalog(
        client,
        tenant_id,
        token,
        barcode=f"5280{uuid4().int % 10**9:09d}",
    )
    opening_at = datetime.now(UTC) - timedelta(days=30)
    opening = _opening(
        client,
        tenant_id,
        token,
        str(customer["id"]),
        opening_amount,
        effective_at=opening_at,
    )
    if corrected_amount is not None:
        _correct(client, tenant_id, token, opening["id"], corrected_amount)

    obligations = _obligations(client, tenant_id, token, customer["id"])
    if expected_obligation is None:
        assert obligations == []
    else:
        assert obligations == [
            {
                "target_ledger_entry_id": opening["id"],
                "source_type": "OPENING_BALANCE",
                "source_id": None,
                "label": "Opening Balance",
                "effective_at": opening["effective_at"],
                "original_amount": expected_obligation,
                "allocated_amount": "0.0000",
                "outstanding_amount": expected_obligation,
            }
        ]

    effective_position = corrected_amount or opening_amount
    balances = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert balances.status_code == 200, balances.text
    assert balances.json()["balances"] == [
        {"currency": "USD", "balance": f"{Decimal(effective_position):.4f}"}
    ]
    debts = client.get(
        "/api/v1/customer-ledger/debts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert debts.status_code == 200, debts.text
    if Decimal(effective_position) > 0:
        assert len(debts.json()["debts"]) == 1
        assert debts.json()["debts"][0]["balance"] == f"{Decimal(effective_position):.4f}"
        assert debts.json()["debts"][0]["oldest_unpaid_at"] == opening["effective_at"]
    else:
        assert debts.json()["debts"] == []

    with session_factory() as db:
        persisted = db.get(CustomerLedgerEntry, UUID(str(opening["id"])))
        assert persisted is not None
        assert type(persisted.entry_type) is str
        assert persisted.entry_type == LedgerEntryType.OPENING_BALANCE


def test_receipt_allocates_once_to_effective_opening_and_updates_balance_and_debt(
    client, session_factory
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "fa008-receipt")
    _category, _product, customer = _catalog(client, tenant_id, token)
    opening_at = datetime.now(UTC) - timedelta(days=30)
    opening = _opening(
        client,
        tenant_id,
        token,
        str(customer["id"]),
        "10.0000",
        effective_at=opening_at,
    )
    _correct(client, tenant_id, token, opening["id"], "12.0000")

    receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "7.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert receipt.status_code == 201, receipt.text
    body = receipt.json()
    assert body["allocated_amount"] == "7.0000"
    assert body["unallocated_amount"] == "0.0000"
    assert body["customer_balance"] == "5.0000"
    assert len(body["allocations"]) == 1
    assert body["allocations"][0]["target_ledger_entry_id"] == opening["id"]
    assert body["allocations"][0]["amount"] == "7.0000"

    assert _obligations(client, tenant_id, token, customer["id"]) == [
        {
            "target_ledger_entry_id": opening["id"],
            "source_type": "OPENING_BALANCE",
            "source_id": None,
            "label": "Opening Balance",
            "effective_at": opening["effective_at"],
            "original_amount": "12.0000",
            "allocated_amount": "7.0000",
            "outstanding_amount": "5.0000",
        }
    ]
    balances = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert balances.status_code == 200, balances.text
    assert balances.json()["balances"] == [{"currency": "USD", "balance": "5.0000"}]
    debts = client.get(
        "/api/v1/customer-ledger/debts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert debts.status_code == 200, debts.text
    assert len(debts.json()["debts"]) == 1
    assert debts.json()["debts"][0]["balance"] == "5.0000"
    assert debts.json()["debts"][0]["oldest_unpaid_at"] == opening["effective_at"]


def test_corrected_opening_and_invoice_remain_distinct_obligations(client, session_factory) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "fa008-invoice")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    opening = _opening(client, tenant_id, token, str(customer["id"]), "10.0000")
    _correct(client, tenant_id, token, opening["id"], "12.0000")

    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/invoices/{created.json()['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": created.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text

    obligations = _obligations(client, tenant_id, token, customer["id"])
    assert len(obligations) == 2
    assert obligations[0]["target_ledger_entry_id"] == opening["id"]
    assert obligations[0]["original_amount"] == "12.0000"
    assert obligations[1]["source_type"] == "INVOICE"
    assert obligations[1]["source_id"] == created.json()["id"]
    assert obligations[1]["original_amount"] == "24.2500"


def test_receipt_reversal_restores_opening_without_creating_a_reversal_obligation(
    client, session_factory
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "fa008-reversal")
    _category, _product, customer = _catalog(client, tenant_id, token)
    opening = _opening(client, tenant_id, token, str(customer["id"]), "10.0000")
    first_receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert first_receipt.status_code == 201, first_receipt.text
    assert _obligations(client, tenant_id, token, customer["id"]) == []

    reversal = client.post(
        f"/api/v1/payments/{first_receipt.json()['id']}/reverse",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"idempotency_key": str(uuid4()), "reason": "Correct duplicated receipt"},
    )
    assert reversal.status_code == 201, reversal.text
    restored = _obligations(client, tenant_id, token, customer["id"])
    assert len(restored) == 1
    assert restored[0]["target_ledger_entry_id"] == opening["id"]
    assert restored[0]["original_amount"] == "10.0000"
    assert restored[0]["allocated_amount"] == "0.0000"
    assert restored[0]["outstanding_amount"] == "10.0000"

    corrected_receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert corrected_receipt.status_code == 201, corrected_receipt.text
    assert corrected_receipt.json()["allocated_amount"] == "10.0000"
    assert corrected_receipt.json()["customer_balance"] == "0.0000"
    assert _obligations(client, tenant_id, token, customer["id"]) == []


def test_refund_compensation_is_not_an_allocatable_customer_obligation(
    client, session_factory
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "fa008-refund")
    _category, _product, customer = _catalog(client, tenant_id, token)
    _opening(client, tenant_id, token, str(customer["id"]), "-10.0000")
    refund = client.post(
        "/api/v1/payments/customer-refunds",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "5.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert refund.status_code == 201, refund.text
    assert refund.json()["customer_balance"] == "-5.0000"
    assert _obligations(client, tenant_id, token, customer["id"]) == []


def test_opening_obligations_are_isolated_by_tenant_and_currency(client, session_factory) -> None:
    _owner_one, tenant_one, token_one = _owner_context(client, session_factory, "fa008-tenant-one")
    _category_one, _product_one, customer_one = _catalog(client, tenant_one, token_one)
    usd_opening = _opening(client, tenant_one, token_one, str(customer_one["id"]), "10.0000")
    _correct(client, tenant_one, token_one, usd_opening["id"], "12.0000")
    eur_opening = _opening(
        client,
        tenant_one,
        token_one,
        str(customer_one["id"]),
        "-10.0000",
        currency="EUR",
    )
    _correct(client, tenant_one, token_one, eur_opening["id"], "5.0000")

    _owner_two, tenant_two, token_two = _owner_context(client, session_factory, "fa008-tenant-two")
    _category_two, _product_two, customer_two = _catalog(
        client,
        tenant_two,
        token_two,
        barcode="5280000000098",
    )
    other_opening = _opening(client, tenant_two, token_two, str(customer_two["id"]), "20.0000")
    _correct(client, tenant_two, token_two, other_opening["id"], "0.0000")

    tenant_one_usd = _obligations(client, tenant_one, token_one, customer_one["id"], "USD")
    tenant_one_eur = _obligations(client, tenant_one, token_one, customer_one["id"], "EUR")
    tenant_two_usd = _obligations(client, tenant_two, token_two, customer_two["id"], "USD")
    assert [(row["target_ledger_entry_id"], row["original_amount"]) for row in tenant_one_usd] == [
        (usd_opening["id"], "12.0000")
    ]
    assert [(row["target_ledger_entry_id"], row["original_amount"]) for row in tenant_one_eur] == [
        (eur_opening["id"], "5.0000")
    ]
    assert tenant_two_usd == []

    cross_tenant = client.get(
        f"/api/v1/payments/customers/{customer_one['id']}/obligations",
        params={"tenant_id": tenant_two, "currency": "USD"},
        headers=_auth(token_two),
    )
    assert cross_tenant.status_code == 404

    with session_factory() as db:
        rows = list(
            db.scalars(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.entry_type == LedgerEntryType.OPENING_BALANCE_CORRECTION
                )
            )
        )
        assert len(rows) == 3
