"""OE-06b read-only business invoice lists, financial projections and compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select, text
from sqlalchemy.orm import Session, sessionmaker
from test_invoice_editor import _auth, _login, _owner_context, _user

from tawzeevo_api.models import (
    AllocationKind,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceStatus,
    LedgerEntryType,
    Payment,
    PaymentAllocation,
    PaymentDirection,
    SystemUserType,
    TenantFinancialSettings,
    TenantMembership,
    TenantRole,
)
from tawzeevo_api.schemas.invoice_lists import BusinessInvoiceListQuery, InvoiceListFilters
from tawzeevo_api.services import invoice_lists
from tawzeevo_api.services.customer_ledger import overdue_calendar_date
from tawzeevo_api.services.customer_lists import list_customer_invoices
from tawzeevo_api.services.text_search import (
    normalize_search_text,
    normalized_search_expression,
)

NOW = datetime(2026, 10, 29, 22, 30, tzinfo=UTC)  # Oct 30 in Beirut, still Oct 29 UTC.
OLD = datetime(2026, 10, 28, 21, 30, tzinfo=UTC)  # Oct 28 in Beirut: calendar age 2.


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return NOW if tz else NOW.replace(tzinfo=None)


@dataclass
class Data:
    tenant: str
    token: str
    owner: UUID
    customer: UUID
    other_customer: UUID
    ids: dict[str, str]


def _seed_invoice(
    db: Session,
    tenant: UUID,
    owner: UUID,
    customer: UUID | None,
    *,
    status: InvoiceStatus = InvoiceStatus.CONFIRMED,
    currency: str = "USD",
    amount: str = "100",
    allocated: str = "0",
    reversed_amount: str = "0",
    delta: str = "0",
    effective_at: datetime = OLD,
    created_at: datetime = OLD,
    number: int = 1,
) -> UUID:
    invoice_id, revision_id = uuid4(), uuid4()
    numbered = status != InvoiceStatus.DRAFT
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant,
        customer_id=customer,
        current_revision_id=revision_id,
        confirmed_revision_id=revision_id if numbered else None,
        status=status,
        official_invoice_number=f"2026-{number:06d}" if numbered else None,
        official_invoice_year=2026 if numbered else None,
        official_sequence_number=number if numbered else None,
        created_by_user_id=owner,
        created_at=created_at,
        confirmed_at=created_at if numbered else None,
        cancelled_at=created_at if status == InvoiceStatus.CANCELLED else None,
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceRevision(
            id=revision_id,
            tenant_id=tenant,
            invoice_id=invoice_id,
            client_command_id=uuid4(),
            server_revision_number=1,
            pricing_version="pricing-v1",
            currency=currency,
            customer_id=customer,
            customer_snapshot={},
            prior_balance_snapshot=Decimal("0"),
            subtotal=Decimal(amount),
            discount_total=Decimal("0"),
            markup_total=Decimal("0"),
            net_sales=Decimal(amount),
            amount_due_display=Decimal(amount),
            created_by_user_id=owner,
        )
    )
    db.flush()
    if not numbered:
        return invoice_id
    entry = CustomerLedgerEntry(
        tenant_id=tenant,
        customer_id=customer,
        currency=currency,
        signed_amount=Decimal(amount),
        entry_type=LedgerEntryType.INVOICE_CHARGE,
        source_type="INVOICE",
        source_id=invoice_id,
        source_effect_key=f"seed-charge:{invoice_id}",
        effective_at=effective_at,
        actor_user_id=owner,
    )
    db.add(entry)
    db.flush()
    adjustment = -Decimal(amount) if status == InvoiceStatus.CANCELLED else Decimal(delta)
    if adjustment:
        db.add(
            CustomerLedgerEntry(
                tenant_id=tenant,
                customer_id=customer,
                currency=currency,
                signed_amount=adjustment,
                entry_type=(
                    LedgerEntryType.INVOICE_REVERSAL
                    if status == InvoiceStatus.CANCELLED
                    else LedgerEntryType.INVOICE_ADJUSTMENT
                ),
                source_type="INVOICE",
                source_id=invoice_id,
                source_effect_key=f"seed-adjustment:{invoice_id}",
                effective_at=effective_at + timedelta(hours=1),
                actor_user_id=owner,
            )
        )
    if Decimal(allocated):
        payment = Payment(
            tenant_id=tenant,
            customer_id=customer,
            currency=currency,
            amount=Decimal(allocated),
            direction=PaymentDirection.CUSTOMER_RECEIPT,
            paid_at=NOW,
            recorded_by_user_id=owner,
            idempotency_key=uuid4(),
        )
        db.add(payment)
        db.flush()
        allocation = PaymentAllocation(
            tenant_id=tenant,
            payment_id=payment.id,
            customer_id=customer,
            currency=currency,
            target_ledger_entry_id=entry.id,
            amount=Decimal(allocated),
            kind=AllocationKind.APPLY,
            created_by_user_id=owner,
            idempotency_key=uuid4(),
        )
        db.add(allocation)
        db.flush()
        if Decimal(reversed_amount):
            db.add(
                PaymentAllocation(
                    tenant_id=tenant,
                    payment_id=payment.id,
                    customer_id=customer,
                    currency=currency,
                    target_ledger_entry_id=entry.id,
                    amount=Decimal(reversed_amount),
                    kind=AllocationKind.REVERSAL,
                    reverses_allocation_id=allocation.id,
                    created_by_user_id=owner,
                    idempotency_key=uuid4(),
                )
            )
    db.flush()
    return invoice_id


@pytest.fixture
def data(
    client: TestClient, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> Data:
    owner, tenant, token = _owner_context(client, session_factory, "business-invoices")
    monkeypatch.setattr(invoice_lists, "datetime", FrozenDatetime)
    with session_factory() as db:
        first = Customer(tenant_id=tenant, name="أحـمَد", phone="+96170123456")
        second = Customer(tenant_id=tenant, name="Cedar Bakery", phone="+96170123457")
        db.add_all([first, second])
        db.flush()
        specs: dict[str, dict[str, Any]] = {
            "unpaid": {},
            # Invoice ledger is 80 after a delta, allocations net 30: remaining 50.
            "partly": {"allocated": "50", "reversed_amount": "20", "delta": "-20"},
            "paid": {"amount": "90", "allocated": "90"},
            "cancelled": {"status": InvoiceStatus.CANCELLED, "amount": "10"},
            "draft": {"status": InvoiceStatus.DRAFT, "amount": "30"},
            "lbp": {"currency": "LBP", "amount": "2000", "customer": second.id},
            # Age exactly threshold 1: not overdue.
            "recent": {"effective_at": datetime(2026, 10, 28, 22, 30, tzinfo=UTC)},
            "anonymous": {"status": InvoiceStatus.DRAFT, "customer": None},
        }
        ids = {}
        for i, (key, spec) in enumerate(specs.items(), 1):
            customer = spec.pop("customer", first.id)
            ids[key] = str(
                _seed_invoice(
                    db,
                    UUID(tenant),
                    owner.id,
                    customer,
                    number=i,
                    created_at=OLD + timedelta(minutes=i),
                    **spec,
                )
            )
        db.add(TenantFinancialSettings(tenant_id=tenant, customer_overdue_threshold_days=1))
        db.commit()
        return Data(tenant, token, owner.id, first.id, second.id, ids)


def _get(client: TestClient, data: Data, suffix: str = "all", **filters: Any) -> dict[str, Any]:
    response = client.get(
        f"/api/v1/invoices/{suffix}",
        params={"tenant_id": data.tenant, **filters},
        headers=_auth(data.token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_positions_paging_order_and_legacy_response(
    client: TestClient, session_factory: sessionmaker[Session], data: Data
) -> None:
    body = _get(client, data)
    assert (body["page"], body["limit"], body["total"], body["total_pages"]) == (1, 20, 8, 1)
    assert [r["id"] for r in body["invoices"]] == list(reversed(data.ids.values()))
    rows = {r["id"]: r for r in body["invoices"]}
    for key, outstanding, state in [
        ("unpaid", "100.0000", "UNPAID"),
        ("partly", "50.0000", "PARTLY_PAID"),
        ("paid", "0.0000", "PAID"),
        ("cancelled", "0.0000", None),
        ("draft", "0.0000", None),
    ]:
        row = rows[data.ids[key]]
        assert (row["outstanding"], row["paid_state"]) == (outstanding, state)
        assert row["customer_id"] == str(data.customer)
        assert row["customer_name"] == "أحـمَد"
    for key in ["cancelled", "draft", "anonymous"]:
        assert rows[data.ids[key]]["is_overdue"] is False
        assert rows[data.ids[key]]["overdue_age_days"] is None
    assert rows[data.ids["anonymous"]]["customer_name"] is None
    paged = _get(client, data, page=2, limit=3)
    assert paged["total"] == 8 and paged["total_pages"] == 3
    assert paged["invoices"] == body["invoices"][3:6]
    assert _get(client, data, page=20)["invoices"] == []
    for params in [{"limit": 101}, {"limit": 0}, {"page": 0}]:
        assert (
            client.get(
                "/api/v1/invoices/all",
                params={"tenant_id": data.tenant, **params},
                headers=_auth(data.token),
            ).status_code
            == 422
        )

    # Byte-for-byte JSON shape/values remain those of the original service.
    with session_factory() as db:
        expected = list_customer_invoices(db, UUID(data.tenant), data.customer, 1, 20)
    legacy = client.get(
        "/api/v1/invoices",
        params={"tenant_id": data.tenant, "customer_id": str(data.customer)},
        headers=_auth(data.token),
    )
    assert legacy.status_code == 200
    assert legacy.json() == expected.model_dump(mode="json")
    assert set(legacy.json()["invoices"][0]) == {
        "id",
        "status",
        "official_invoice_number",
        "confirmed_at",
        "created_at",
        "currency",
        "net_sales",
        "total_due",
        "server_revision_number",
    }
    missing = client.get(
        "/api/v1/invoices",
        params={"tenant_id": data.tenant, "customer_id": str(uuid4())},
        headers=_auth(data.token),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_every_filter_and_combined_filters(client: TestClient, data: Data) -> None:
    cases = [
        ({"status": "DRAFT"}, {"draft", "anonymous"}),
        ({"status": "CONFIRMED"}, {"unpaid", "partly", "paid", "lbp", "recent"}),
        ({"status": "CANCELLED"}, {"cancelled"}),
        ({"paid_state": "UNPAID"}, {"unpaid", "lbp", "recent"}),
        ({"paid_state": "PARTLY_PAID"}, {"partly"}),
        ({"paid_state": "PAID"}, {"paid"}),
        ({"paid_state": "OPEN"}, {"unpaid", "partly", "lbp", "recent"}),
        ({"overdue": True}, {"unpaid", "partly", "lbp"}),
        ({"overdue": False}, {"paid", "cancelled", "draft", "recent", "anonymous"}),
        ({"customer_id": str(data.other_customer)}, {"lbp"}),
        ({"currency": "LBP"}, {"lbp"}),
        # OLD is Oct 28 in Beirut. Both bounds are inclusive calendar dates.
        ({"date_from": "2026-10-28"}, set(data.ids)),
        ({"date_to": "2026-10-28"}, set(data.ids)),
        ({"date_from": "2026-10-29"}, set()),
        ({"date_to": "2026-10-27"}, set()),
        ({"q": "CEDAR"}, {"lbp"}),
        ({"overdue": True, "currency": "USD"}, {"unpaid", "partly"}),
        ({"paid_state": "OPEN", "customer_id": str(data.other_customer)}, {"lbp"}),
    ]
    for filters, keys in cases:
        body = _get(client, data, **filters)
        assert {r["id"] for r in body["invoices"]} == {data.ids[k] for k in keys}, filters
        assert body["total"] == len(keys), filters
    for filters in [{"status": "invalid"}, {"paid_state": "invalid"}, {"date_to": "bad"}]:
        assert (
            client.get(
                "/api/v1/invoices/all",
                params={"tenant_id": data.tenant, **filters},
                headers=_auth(data.token),
            ).status_code
            == 422
        )


def test_arabic_normalization_and_literal_search(
    client: TestClient, session_factory: sessionmaker[Session], data: Data
) -> None:
    for q in ["احمد", "إحمد", "آحمد", "ٱحمد", "أحـمَد"]:
        rows = _get(client, data, q=q)["invoices"]
        assert len(rows) == 6
        assert {r["customer_id"] for r in rows} == {str(data.customer)}
    for q in ["٢٠٢٦-٠٠٠٠٠١", "۲۰۲۶-۰۰۰۰۰۱", "2026-000001"]:
        assert [r["id"] for r in _get(client, data, q=q)["invoices"]] == [data.ids["unpaid"]]
    for q in ["%", "_", "' OR true --"]:
        assert _get(client, data, q=q)["invoices"] == []
    # Exercise every requested folding rule against the SQL expression as well as Python.
    samples = ["أإآٱىةـًٌٍَُِّْ٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "CeDaR"]
    with session_factory() as db:
        from sqlalchemy import literal

        for value in samples:
            assert db.scalar(select(normalized_search_expression(literal(value)))) == (
                normalize_search_text(value)
            )
    assert normalize_search_text(samples[0]) == "اااايه01234567890123456789"


def test_beirut_age_threshold_disabled_and_date_boundary(
    client: TestClient, session_factory: sessionmaker[Session], data: Data
) -> None:
    assert overdue_calendar_date(NOW).isoformat() == "2026-10-30"
    rows = {r["id"]: r for r in _get(client, data)["invoices"]}
    assert rows[data.ids["unpaid"]]["overdue_age_days"] == 2
    assert rows[data.ids["unpaid"]]["is_overdue"] is True
    assert rows[data.ids["recent"]]["overdue_age_days"] == 1
    assert rows[data.ids["recent"]]["is_overdue"] is False
    assert rows[data.ids["paid"]]["is_overdue"] is False
    with session_factory() as db:
        settings = db.get(TenantFinancialSettings, UUID(data.tenant))
        assert settings
        settings.customer_overdue_threshold_days = None
        # The coalesced confirmed_at, rather than created_at, crosses the Beirut date.
        invoice = db.get(Invoice, UUID(data.ids["recent"]))
        assert invoice
        invoice.confirmed_at = datetime(2026, 10, 28, 22, 0, tzinfo=UTC)
        db.commit()
    assert _get(client, data, overdue=True)["total"] == 0
    rows = {r["id"]: r for r in _get(client, data)["invoices"]}
    assert rows[data.ids["unpaid"]]["overdue_age_days"] == 2
    assert not any(r["is_overdue"] for r in rows.values())
    assert [
        r["id"]
        for r in _get(client, data, date_from="2026-10-29", date_to="2026-10-29")["invoices"]
    ] == [data.ids["recent"]]
    with session_factory() as db:
        settings = db.get(TenantFinancialSettings, UUID(data.tenant))
        assert settings
        db.delete(settings)
        db.commit()
    assert _get(client, data, overdue=True)["total"] == 0


def test_summary_equals_filtered_rows_per_currency(client: TestClient, data: Data) -> None:
    for filters in [
        {},
        {"overdue": True},
        {"paid_state": "OPEN"},
        {"status": "DRAFT"},
        {"currency": "USD", "customer_id": str(data.customer)},
        {"q": "احمد"},
        {"date_from": "2026-10-29"},
    ]:
        rows = _get(client, data, **filters)["invoices"]
        summary = _get(client, data, "summary", **filters)["currencies"]
        assert {s["currency"] for s in summary} == {r["currency"] for r in rows}
        for group in summary:
            selected = [r for r in rows if r["currency"] == group["currency"]]
            assert Decimal(group["outstanding_total"]) == sum(
                (Decimal(r["outstanding"]) for r in selected), Decimal(0)
            )
            assert Decimal(group["overdue_total"]) == sum(
                (Decimal(r["outstanding"]) for r in selected if r["is_overdue"]), Decimal(0)
            )
            assert group["open_count"] == sum(Decimal(r["outstanding"]) > 0 for r in selected)
            assert group["overdue_count"] == sum(r["is_overdue"] for r in selected)
            assert group["paid_count"] == sum(r["paid_state"] == "PAID" for r in selected)
            assert group["draft_count"] == sum(r["status"] == "DRAFT" for r in selected)
    totals = {s["currency"]: s for s in _get(client, data, "summary")["currencies"]}
    assert totals["USD"]["outstanding_total"] == "250.0000"
    assert totals["USD"]["overdue_total"] == "150.0000"
    assert totals["LBP"]["outstanding_total"] == "2000.0000"


def test_tenant_isolation_and_owner_only(
    client: TestClient, session_factory: sessionmaker[Session], data: Data
) -> None:
    other_owner, other_tenant, other_token = _owner_context(
        client, session_factory, "other-invoices"
    )
    with session_factory() as db:
        customer = Customer(tenant_id=other_tenant, name="Other business", phone="+96170987654")
        db.add(customer)
        db.flush()
        other_id = _seed_invoice(db, UUID(other_tenant), other_owner.id, customer.id)
        db.commit()
    assert str(other_id) not in {r["id"] for r in _get(client, data)["invoices"]}
    for endpoint in ["all", "summary"]:
        other = client.get(
            f"/api/v1/invoices/{endpoint}",
            params={"tenant_id": other_tenant, "customer_id": str(data.customer)},
            headers=_auth(other_token),
        )
        assert other.status_code == 200
        assert other.json().get("total", 0) == 0
        assert other.json().get("currencies", []) == []
        forbidden = client.get(
            f"/api/v1/invoices/{endpoint}",
            params={"tenant_id": data.tenant},
            headers=_auth(other_token),
        )
        assert forbidden.status_code == 403
        assert (
            client.get(
                f"/api/v1/invoices/{endpoint}", params={"tenant_id": data.tenant}
            ).status_code
            == 401
        )

    driver = _user(session_factory, "invoice-driver@example.com", SystemUserType.CLIENT)
    with session_factory() as db:
        db.add(TenantMembership(tenant_id=data.tenant, user_id=driver.id, role=TenantRole.DRIVER))
        db.commit()
    driver_token = _login(client, driver.email)
    for endpoint in ["", "/all", "/summary"]:
        denied = client.get(
            f"/api/v1/invoices{endpoint}",
            params={"tenant_id": data.tenant, "customer_id": str(data.customer)},
            headers=_auth(driver_token),
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "TENANT_OWNER_REQUIRED"


def test_tied_timestamps_use_id_descending(
    client: TestClient, session_factory: sessionmaker[Session], data: Data
) -> None:
    with session_factory() as db:
        for invoice in db.scalars(select(Invoice).where(Invoice.tenant_id == UUID(data.tenant))):
            invoice.created_at = OLD
            if invoice.confirmed_at:
                invoice.confirmed_at = OLD
        db.commit()
    assert [r["id"] for r in _get(client, data)["invoices"]] == sorted(
        data.ids.values(), reverse=True
    )


def test_bounded_queries_and_explain_on_3000_invoices(
    session_factory: sessionmaker[Session], data: Data
) -> None:
    """Synthetic local performance evidence, using real tables, constraints and query builder."""
    tenant = UUID(data.tenant)
    headers, revisions, entries, allocations = [], [], [], []
    payment_id = uuid4()
    for i in range(3000):
        invoice_id, revision_id, entry_id, allocation_id = uuid4(), uuid4(), uuid4(), uuid4()
        headers.append(
            {
                "id": invoice_id,
                "tenant_id": tenant,
                "customer_id": data.customer,
                "current_revision_id": revision_id,
                "confirmed_revision_id": revision_id,
                "status": InvoiceStatus.CONFIRMED,
                "official_invoice_number": f"2026-{i + 100:06d}",
                "official_invoice_year": 2026,
                "official_sequence_number": i + 100,
                "created_by_user_id": data.owner,
                "created_at": OLD,
                "confirmed_at": OLD,
            }
        )
        revisions.append(
            {
                "id": revision_id,
                "tenant_id": tenant,
                "invoice_id": invoice_id,
                "client_command_id": uuid4(),
                "server_revision_number": 1,
                "pricing_version": "pricing-v1",
                "currency": "USD",
                "customer_id": data.customer,
                "customer_snapshot": {},
                "prior_balance_snapshot": Decimal(0),
                "subtotal": Decimal(100),
                "discount_total": Decimal(0),
                "markup_total": Decimal(0),
                "net_sales": Decimal(100),
                "amount_due_display": Decimal(100),
                "created_by_user_id": data.owner,
            }
        )
        entries.append(
            {
                "id": entry_id,
                "tenant_id": tenant,
                "customer_id": data.customer,
                "currency": "USD",
                "signed_amount": Decimal(100),
                "entry_type": LedgerEntryType.INVOICE_CHARGE,
                "source_type": "INVOICE",
                "source_id": invoice_id,
                "source_effect_key": f"perf:{invoice_id}",
                "effective_at": OLD,
                "actor_user_id": data.owner,
            }
        )
        common = {
            "tenant_id": tenant,
            "customer_id": data.customer,
            "currency": "USD",
            "payment_id": payment_id,
            "target_ledger_entry_id": entry_id,
            "created_by_user_id": data.owner,
        }
        allocations.extend(
            [
                {
                    **common,
                    "id": allocation_id,
                    "amount": Decimal(20),
                    "kind": AllocationKind.APPLY,
                    "idempotency_key": uuid4(),
                    "reverses_allocation_id": None,
                },
                {
                    **common,
                    "id": uuid4(),
                    "amount": Decimal(10),
                    "kind": AllocationKind.REVERSAL,
                    "idempotency_key": uuid4(),
                    "reverses_allocation_id": allocation_id,
                },
            ]
        )
    with session_factory() as db:
        db.execute(insert(Invoice), headers)
        db.execute(insert(InvoiceRevision), revisions)
        db.execute(insert(CustomerLedgerEntry), entries)
        db.add(
            Payment(
                id=payment_id,
                tenant_id=tenant,
                customer_id=data.customer,
                currency="USD",
                amount=Decimal(60000),
                direction=PaymentDirection.CUSTOMER_RECEIPT,
                paid_at=NOW,
                recorded_by_user_id=data.owner,
                idempotency_key=uuid4(),
            )
        )
        db.flush()
        db.execute(insert(PaymentAllocation).execution_options(render_nulls=True), allocations)
        db.commit()

    statements: list[tuple[str, Any]] = []

    def capture(
        connection: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        statements.append((statement, parameters))

    with session_factory() as db:
        connection = db.connection()
        event.listen(connection, "before_cursor_execute", capture)
        try:
            result = invoice_lists.list_business_invoices(
                db, tenant, BusinessInvoiceListQuery(paid_state="OPEN", overdue=True, page=100)
            )
            assert result.total == 3003 and len(result.invoices) == 20
            assert len(statements) == 3  # settings + count + page, independent of invoice count.
            assert all(s.lstrip().upper().startswith(("SELECT", "WITH")) for s, _ in statements)
            count_query, page_query = statements[1:]
            statements.clear()
            invoice_lists.summarize_business_invoices(
                db, tenant, InvoiceListFilters(paid_state="OPEN", overdue=True)
            )
            assert len(statements) == 2  # settings + grouped summary.
            summary_query = statements[1]
        finally:
            event.remove(connection, "before_cursor_execute", capture)

        # EXPLAIN uses the same filters, financial CTEs and order as the production page.
        for table in [
            "invoices",
            "invoice_revisions",
            "customer_ledger_entries",
            "payment_allocations",
        ]:
            db.execute(text(f"ANALYZE {table}"))
        # Replay the exact statements and parameters captured from the production services.
        queries = {"page": page_query, "count": count_query, "summary": summary_query}
        for name, (statement, parameters) in queries.items():
            plan = connection.exec_driver_sql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
            ).scalar_one()[0]
            scans = []

            def visit(node: dict[str, Any], scans: list[dict[str, Any]] = scans) -> None:
                if "Relation Name" in node:
                    scans.append(
                        {
                            "table": node["Relation Name"],
                            "scan": node["Node Type"],
                            "rows": node["Actual Rows"],
                            "loops": node["Actual Loops"],
                        }
                    )
                for child in node.get("Plans", []):
                    visit(child)

            visit(plan["Plan"])
            print(f"OE-06b EXPLAIN {name}: {plan['Execution Time']} ms; scans={scans}")
