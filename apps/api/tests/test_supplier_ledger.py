from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_invoice_editor import _auth, _owner_context

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import Payment, PaymentAllocation, SupplierLedgerEntry, TenantSupplier
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.payments import PaymentReversalRequest
from tawzeevo_api.services.supplier_ledger import reverse_supplier_payment


def _supplier_context(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "supplier-ledger")
    with session_factory() as db:
        supplier = TenantSupplier(tenant_id=tenant, name="Independent tenant supplier")
        db.add(supplier)
        db.commit()
        supplier_id = str(supplier.id)
    return owner, tenant, token, supplier_id


def _payable(client, tenant, token, supplier, currency="USD", amount="10.0000"):
    """Give the supplier a positive payable so ordinary payments are allowed (D-039)."""
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


def test_supplier_payment_aggregate_balance_replay_reversal_and_currency(client, session_factory):
    _, tenant, token, supplier = _supplier_context(client, session_factory)
    headers = _auth(token)
    for currency, amount in (("USD", "20.0000"), ("LBP", "500000.0000")):
        opening = {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier,
            "currency": currency,
            "signed_amount": amount,
            "effective_at": datetime.now(UTC).isoformat(),
        }
        first = client.post(
            f"/api/v1/supplier-ledger/opening-balances?tenant_id={tenant}",
            headers=headers,
            json=opening,
        )
        assert first.status_code == 201, first.text
        assert (
            client.post(
                f"/api/v1/supplier-ledger/opening-balances?tenant_id={tenant}",
                headers=headers,
                json=opening,
            ).json()
            == first.json()
        )
    payload = {
        "idempotency_key": str(uuid4()),
        "supplier_id": supplier,
        "currency": "USD",
        "amount": "7.0000",
        "paid_at": datetime.now(UTC).isoformat(),
        "method": "CASH",
    }
    path = f"/api/v1/payments/supplier-payments?tenant_id={tenant}"
    paid = client.post(path, headers=headers, json=payload)
    assert paid.status_code == 201, paid.text
    assert client.post(path, headers=headers, json=payload).json() == paid.json()
    changed = {**payload, "reference": "different command"}
    assert client.post(path, headers=headers, json=changed).status_code == 409
    balances = client.get(
        f"/api/v1/supplier-ledger/{supplier}/balances?tenant_id={tenant}", headers=headers
    ).json()["balances"]
    assert {b["currency"]: b["balance"] for b in balances} == {
        "USD": "13.0000",
        "LBP": "500000.0000",
    }
    reverse_path = (
        f"/api/v1/payments/supplier-payments/{paid.json()['id']}/reverse?tenant_id={tenant}"
    )
    reversal = {"idempotency_key": str(uuid4()), "reason": "Wrong receipt entered"}
    reversed_payment = client.post(reverse_path, headers=headers, json=reversal)
    assert reversed_payment.status_code == 201, reversed_payment.text
    assert (
        client.post(reverse_path, headers=headers, json=reversal).json() == reversed_payment.json()
    )
    assert (
        client.post(
            reverse_path, headers=headers, json={**reversal, "idempotency_key": str(uuid4())}
        ).status_code
        == 409
    )
    balances = client.get(
        f"/api/v1/supplier-ledger/{supplier}/balances?tenant_id={tenant}", headers=headers
    ).json()["balances"]
    assert {b["currency"]: b["balance"] for b in balances}["USD"] == "20.0000"
    with session_factory() as db:
        assert len(list(db.scalars(select(Payment)))) == 2
        assert list(db.scalars(select(PaymentAllocation))) == []
        entries = list(db.scalars(select(SupplierLedgerEntry)))
        assert len(entries) == 4 and sum(
            e.signed_amount for e in entries if e.currency == "USD"
        ) == Decimal("20")
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                text("UPDATE payments SET amount = 1 WHERE id = :id"), {"id": paid.json()["id"]}
            )
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                text("DELETE FROM supplier_ledger_entries WHERE id = :id"), {"id": entries[0].id}
            )


def test_supplier_cross_tenant_rejected_and_reversal_serialized(client, session_factory):
    owner, tenant, token, supplier = _supplier_context(client, session_factory)
    _payable(client, tenant, token, supplier)
    _, other, other_token = _owner_context(client, session_factory, "supplier-other")
    payload = {
        "idempotency_key": str(uuid4()),
        "supplier_id": supplier,
        "currency": "USD",
        "amount": "2.2500",
        "paid_at": datetime.now(UTC).isoformat(),
    }
    assert (
        client.post(
            f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
            headers=_auth(other_token),
            json=payload,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/payments/supplier-payments?tenant_id={other}",
            headers=_auth(other_token),
            json=payload,
        ).status_code
        == 404
    )
    paid = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}", headers=_auth(token), json=payload
    )
    assert paid.status_code == 201, paid.text
    payment_id = UUID(paid.json()["id"])

    def reverse():
        with session_factory() as db:
            set_tenant_scope(db, UUID(tenant))
            try:
                reverse_supplier_payment(
                    db,
                    UUID(tenant),
                    owner.id,
                    payment_id,
                    PaymentReversalRequest(idempotency_key=uuid4(), reason="Correction"),
                )
                return 201
            except AppError as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: reverse(), range(2))) == [201, 409]
    with session_factory() as db:
        rows = list(db.scalars(select(SupplierLedgerEntry)))
        # opening payable (+10) plus one payment and exactly one reversal that cancel out
        assert len(rows) == 3 and sum(row.signed_amount for row in rows) == Decimal("10")


def test_supplier_payment_schema_rejects_allocations_and_naive_timestamps(client, session_factory):
    _, tenant, token, supplier = _supplier_context(client, session_factory)
    path = f"/api/v1/payments/supplier-payments?tenant_id={tenant}"
    payload = {
        "idempotency_key": str(uuid4()),
        "supplier_id": supplier,
        "currency": "USD",
        "amount": "1.0000",
        "paid_at": "2026-09-05T12:00:00",
    }
    assert client.post(path, headers=_auth(token), json=payload).status_code == 422
    payload["paid_at"] += "Z"
    assert (
        client.post(path, headers=_auth(token), json={**payload, "allocations": []}).status_code
        == 422
    )
    assert (
        client.post(path, headers=_auth(token), json={**payload, "amount": "0"}).status_code == 422
    )


def test_supplier_ledger_forced_rls_hides_other_tenant_and_rejects_insert(
    client,
    session_factory,
    test_engine,
):
    owner, tenant, token, supplier = _supplier_context(client, session_factory)
    _payable(client, tenant, token, supplier)
    payload = {
        "idempotency_key": str(uuid4()),
        "supplier_id": supplier,
        "currency": "USD",
        "amount": "1.0000",
        "paid_at": datetime.now(UTC).isoformat(),
    }
    paid = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}", headers=_auth(token), json=payload
    )
    assert paid.status_code == 201
    role = f"tawzeevo_supplier_test_{uuid4().hex}"
    with test_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        connection.exec_driver_sql(
            f'GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO "{role}"'
        )
    try:
        with test_engine.connect() as connection:
            connection.exec_driver_sql(f'SET ROLE "{role}"')
            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": tenant}
            )
            # opening payable entry plus the payment entry are visible to the owning tenant
            assert len(list(connection.execute(select(SupplierLedgerEntry.id)))) == 2
            assert len(list(connection.execute(select(Payment.id)))) == 1
            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(uuid4())}
            )
            assert list(connection.execute(select(SupplierLedgerEntry.id))) == []
            assert list(connection.execute(select(Payment.id))) == []
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO supplier_ledger_entries "
                        "(id, tenant_id, supplier_id, currency, signed_amount, entry_type, "
                        "source_type, source_effect_key, effective_at, metadata_json) VALUES "
                        "(:id, :tenant, :supplier, 'USD', 1, 'OPENING_BALANCE', 'TEST', 'blocked', "
                        "now(), '{}')"
                    ),
                    {"id": uuid4(), "tenant": tenant, "supplier": supplier},
                )
            connection.rollback()
    finally:
        with test_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP OWNED BY "{role}"')
            connection.exec_driver_sql(f'DROP ROLE "{role}"')


def _pay(client, tenant, token, supplier, amount, currency="USD", prepayment=False):
    kind = "supplier-prepayments" if prepayment else "supplier-payments"
    response = client.post(
        f"/api/v1/payments/{kind}?tenant_id={tenant}",
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier,
            "currency": currency,
            "amount": amount,
            "paid_at": datetime.now(UTC).isoformat(),
            "method": "CASH",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_all_supplier_balances_and_the_payment_history_d100(client, session_factory):
    _, tenant, token, supplier = _supplier_context(client, session_factory)
    headers = _auth(token)
    with session_factory() as db:
        quiet = TenantSupplier(tenant_id=tenant, name="Another supplier")
        db.add(quiet)
        db.commit()
        quiet_id = str(quiet.id)
    _payable(client, tenant, token, supplier, "USD", "30.0000")
    _payable(client, tenant, token, supplier, "LBP", "900000.0000")
    first = _pay(client, tenant, token, supplier, "5.0000")
    _pay(client, tenant, token, supplier, "7.0000")
    credit = _pay(client, tenant, token, supplier, "2.0000", prepayment=True)
    reversal = client.post(
        f"/api/v1/payments/supplier-payments/{first['id']}/reverse?tenant_id={tenant}",
        headers=headers,
        json={"idempotency_key": str(uuid4()), "reason": "Entered twice"},
    )
    assert reversal.status_code == 201, reversal.text

    # Balances: every supplier (also one without entries), per currency, never summed across them.
    listed = client.get(f"/api/v1/supplier-ledger/balances?tenant_id={tenant}", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = {row["supplier_id"]: row for row in listed.json()["suppliers"]}
    assert {b["currency"]: b["balance"] for b in rows[supplier]["balances"]} == {
        "USD": "21.0000",  # 30 - 5 - 7 - 2 (credit) + 5 (the reversal gives the 5 back)
        "LBP": "900000.0000",
    }
    assert rows[quiet_id]["balances"] == []
    assert [row["supplier_name"] for row in listed.json()["suppliers"]] == [
        "Another supplier",
        "Independent tenant supplier",
    ]

    # History: newest first, paginated, with the reversal and prepayment flags.
    page = client.get(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}&supplier_id={supplier}&limit=2",
        headers=headers,
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert (body["total"], body["total_pages"], len(body["payments"])) == (4, 2, 2)
    everything = client.get(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}&limit=100", headers=headers
    ).json()["payments"]
    by_id = {row["id"]: row for row in everything}
    assert by_id[first["id"]]["reversed_by_payment_id"] == reversal.json()["id"]
    assert by_id[reversal.json()["id"]]["reverses_payment_id"] == first["id"]
    assert by_id[credit["id"]]["prepayment"] is True
    assert by_id[first["id"]]["prepayment"] is False
    assert all(row["supplier_name"] == "Independent tenant supplier" for row in everything)

    missing = client.get(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}&supplier_id={uuid4()}",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"


def test_supplier_lists_never_show_another_business(client, session_factory):
    _, tenant, token, supplier = _supplier_context(client, session_factory)
    _payable(client, tenant, token, supplier, "USD", "10.0000")
    _pay(client, tenant, token, supplier, "1.0000")
    _, other_tenant, other_token = _owner_context(client, session_factory, "supplier-ledger-2")
    theirs = client.get(
        f"/api/v1/supplier-ledger/balances?tenant_id={other_tenant}", headers=_auth(other_token)
    ).json()
    assert theirs["suppliers"] == []
    history = client.get(
        f"/api/v1/payments/supplier-payments?tenant_id={other_tenant}", headers=_auth(other_token)
    ).json()
    assert history["total"] == 0
    foreign = client.get(
        f"/api/v1/payments/supplier-payments?tenant_id={other_tenant}&supplier_id={supplier}",
        headers=_auth(other_token),
    )
    assert foreign.status_code == 404
