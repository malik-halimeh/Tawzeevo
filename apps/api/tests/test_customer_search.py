"""OE-03b: bounded owner-only customer search, sorting and positive balances."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker
from test_customer_lists import _customer
from test_invoice_editor import _auth, _login, _owner_context, _user

from tawzeevo_api.models import (
    Customer,
    CustomerLedgerEntry,
    LedgerEntryType,
    SystemUserType,
    TenantMembership,
    TenantRole,
)
from tawzeevo_api.services.customer_lists import list_customers


def test_name_and_partial_phone_search(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _, tenant, token = _owner_context(client, session_factory, "search")
    arabic = _customer(client, tenant, token, "أَحْمَد مدرسة مصطفى", "+961 3 123 456")
    english = _customer(client, tenant, token, "Cedar Bakery", "+961 70 987 654")
    literal = _customer(client, tenant, token, "Shop %_ /", "+961 70 222 333")
    url = f"/api/v1/tenants/{tenant}/customers"
    cases = [
        ("احمد", [arabic]),
        ("أحمد", [arabic]),
        ("أَحْمَد", [arabic]),
        ("مدرسه", [arabic]),
        ("مدرسة", [arabic]),
        ("مصطفي", [arabic]),
        ("مصطفى", [arabic]),
        ("cEDar", [english]),
        ("123", [arabic]),
        ("03 123 456", [arabic]),
        ("3 123 456", [arabic]),
        ("٠٣ ١٢٣ ٤٥٦", [arabic]),
        ("۰۰۳۱۲۳۴۵۶", [arabic]),
        ("12", []),
        ("١٢", []),
        ("0", []),
        ("000", []),
        ("%_", [literal]),
        ("/", [literal]),
        ("missing", []),
    ]
    for query, expected in cases:
        response = client.get(url, headers=_auth(token), params={"q": query})
        assert response.status_code == 200, response.text
        body = response.json()
        assert [row["id"] for row in body["customers"]] == expected, query
        assert body["total"] == len(expected)
        assert body["total_pages"] == bool(expected)

    # Short numeric queries still match names, but cannot broaden to phone matches.
    named = _customer(client, tenant, token, "Shop 12", "+961 70 444 555")
    response = client.get(url, headers=_auth(token), params={"q": "12"})
    assert [row["id"] for row in response.json()["customers"]] == [named]
    for invalid in ({"q": ""}, {"q": "a" * 65}, {"sort": "balance"}, {"page": 0}, {"limit": 101}):
        assert client.get(url, headers=_auth(token), params=invalid).status_code == 422


def test_filtered_paging_and_default_response(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _, tenant, token = _owner_context(client, session_factory, "search-pages")
    names = ["shop Z", "Shop a", "sHOP a", "Unrelated"]
    ids = [_customer(client, tenant, token, name, "+961 70 123 456") for name in names]
    url = f"/api/v1/tenants/{tenant}/customers"
    expected = [*sorted(ids[1:3]), ids[0]]
    for page in (1, 2, 3, 4):
        response = client.get(
            url, headers=_auth(token), params={"q": "shop", "page": page, "limit": 1}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["page"], body["limit"], body["total"], body["total_pages"]) == (page, 1, 3, 3)
        assert [row["id"] for row in body["customers"]] == expected[page - 1 : page]

    default = client.get(url, headers=_auth(token)).json()
    explicit = client.get(url, headers=_auth(token), params={"sort": "name"}).json()
    assert default == explicit
    assert (default["page"], default["limit"], default["total"], default["total_pages"]) == (
        1,
        20,
        4,
        1,
    )
    assert [row["id"] for row in default["customers"]] == [*expected, ids[3]]
    for row in default["customers"]:
        original = client.get(f"{url}/{row['id']}", headers=_auth(token)).json()
        assert row == {**original, "balances": []}


def _entry(db: Session, tenant: str, customer: str, currency: str, amount: str) -> None:
    db.add(
        CustomerLedgerEntry(
            tenant_id=UUID(tenant),
            customer_id=UUID(customer),
            currency=currency,
            signed_amount=Decimal(amount),
            entry_type=LedgerEntryType.INVOICE_ADJUSTMENT,
            source_type="INVOICE",
            source_effect_key=str(uuid4()),
            effective_at=datetime(2026, 10, 29, tzinfo=UTC),
        )
    )


def test_customer_sorts_use_net_positive_single_currency_balances(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _, tenant, token = _owner_context(client, session_factory, "sort")
    names = ["Zulu", "Bravo", "Delta", "Alpha", "Charlie", "Echo", "Foxtrot"]
    ids = [_customer(client, tenant, token, name, "+961 70 123 456") for name in names]
    with session_factory() as db:
        for index, customer_id in enumerate(ids):
            customer = db.get(Customer, UUID(customer_id))
            assert customer is not None
            customer.created_at = datetime(2026, 10, 1, tzinfo=UTC) + timedelta(days=index // 2)
        # Sum each currency first; neither sum of currencies nor largest individual entry.
        for index, currency, amount in [
            (0, "USD", "200"),
            (0, "USD", "-110"),
            (0, "LBP", "90"),
            (1, "USD", "100"),
            (2, "USD", "100"),
            (3, "USD", "-200"),
            (3, "LBP", "110"),
            (4, "USD", "10"),
            (4, "USD", "-10"),
            (5, "USD", "-50"),
        ]:
            _entry(db, tenant, ids[index], currency, amount)
        db.commit()
    url = f"/api/v1/tenants/{tenant}/customers"
    newest = [ids[6], *sorted(ids[4:6]), *sorted(ids[2:4]), *sorted(ids[0:2])]
    expected_owes = [ids[3], ids[1], ids[2], ids[0], ids[4], ids[5], ids[6]]
    for sort, expected in [
        ("name", [ids[i] for i in [3, 1, 4, 2, 5, 6, 0]]),
        ("newest", newest),
        ("owes_most", expected_owes),
    ]:
        response = client.get(url, headers=_auth(token), params={"sort": sort})
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["customers"]] == expected
    rows = {row["id"]: row for row in response.json()["customers"]}
    assert rows[ids[0]]["balances"] == [
        {"currency": "LBP", "balance": "90.0000"},
        {"currency": "USD", "balance": "90.0000"},
    ]
    assert rows[ids[3]]["balances"] == [{"currency": "LBP", "balance": "110.0000"}]
    assert all(rows[ids[i]]["balances"] == [] for i in [4, 5, 6])
    for page in (1, 2, 3, 4):
        body = client.get(
            url, headers=_auth(token), params={"sort": "owes_most", "limit": 2, "page": page}
        ).json()
        assert [row["id"] for row in body["customers"]] == expected_owes[(page - 1) * 2 : page * 2]


def test_search_and_balances_are_tenant_scoped_and_owner_only(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _, tenant, token = _owner_context(client, session_factory, "search-auth")
    _, other_tenant, other_token = _owner_context(client, session_factory, "search-other")
    own = _customer(client, tenant, token, "Same Shop", "+961 3 123 456")
    foreign = _customer(client, other_tenant, other_token, "Same Shop", "+961 3 123 456")
    driver = _user(session_factory, "search-driver@example.com", SystemUserType.CLIENT)
    admin = _user(session_factory, "search-admin@example.com", SystemUserType.ADMIN)
    with session_factory() as db:
        _entry(db, tenant, own, "USD", "5")
        _entry(db, other_tenant, foreign, "USD", "9999")
        db.add(TenantMembership(tenant_id=UUID(tenant), user_id=driver.id, role=TenantRole.DRIVER))
        db.commit()
    url = f"/api/v1/tenants/{tenant}/customers"
    for query in ("shop", "٠٣١٢٣٤٥٦"):
        for sort in ("name", "newest", "owes_most"):
            response = client.get(url, headers=_auth(token), params={"q": query, "sort": sort})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["total"] == 1
            assert [row["id"] for row in body["customers"]] == [own]
            assert body["customers"][0]["balances"] == [{"currency": "USD", "balance": "5.0000"}]
    for denied_token in (other_token, _login(client, driver.email), _login(client, admin.email)):
        response = client.get(
            url, headers=_auth(denied_token), params={"q": "shop", "sort": "owes_most"}
        )
        assert response.status_code == 403, response.text
    assert client.get(url, params={"q": "shop"}).status_code == 401

    # The separate exact normalized phone endpoint retains its shape and matching semantics.
    exact = client.get(f"{url}/search", headers=_auth(token), params={"phone": "03 123 456"})
    original = client.get(f"{url}/{own}", headers=_auth(token)).json()
    assert exact.status_code == 200
    assert exact.json() == {"customers": [original]}
    partial = client.get(f"{url}/search", headers=_auth(token), params={"phone": "123"})
    assert partial.status_code == 400


def test_balances_use_one_grouped_query_per_page(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _, tenant, token = _owner_context(client, session_factory, "search-bounded")
    for index in range(5):
        customer = _customer(client, tenant, token, f"Shop {index}", "+961 70 123 456")
        with session_factory() as db:
            _entry(db, tenant, customer, "USD", "12")
            db.commit()
    statements: list[str] = []

    def capture(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        statements.append(statement)

    with session_factory() as db:
        connection = db.connection()
        event.listen(connection, "before_cursor_execute", capture)
        try:
            for sort in ("name", "newest", "owes_most"):
                statements.clear()
                result = list_customers(db, UUID(tenant), 2, 2, q="shop", sort=sort)
                assert result.total == 5 and len(result.customers) == 2
                assert all(row.balances[0].balance == Decimal("12") for row in result.customers)
                assert len(statements) == 3  # Count, SQL-paged rows, grouped page balances.
                assert "LIMIT" in statements[1] and "OFFSET" in statements[1]
                assert "GROUP BY" in statements[2] and " IN (" in statements[2]
        finally:
            event.remove(connection, "before_cursor_execute", capture)
