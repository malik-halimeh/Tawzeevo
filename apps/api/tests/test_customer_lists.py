"""D-101: the owner's customers list and each customer's invoices (read-only lists)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _draft_payload,
    _owner_context,
)


def _customer(client: TestClient, tenant_id: str, token: str, name: str, phone: str) -> str:
    created = client.post(
        f"/api/v1/tenants/{tenant_id}/customers",
        headers=_auth(token),
        json={"name": name, "phone": phone},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def test_customers_list_pages_by_name(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "custlist")
    _customer(client, tenant_id, token, "beirut bakery", "+961 70 111 201")
    _customer(client, tenant_id, token, "Anjar Farms", "+961 70 111 202")
    _customer(client, tenant_id, token, "Cedar Shop", "+961 70 111 203")

    first = client.get(
        f"/api/v1/tenants/{tenant_id}/customers", headers=_auth(token), params={"limit": 2}
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["page"], body["limit"], body["total"], body["total_pages"]) == (1, 2, 3, 2)
    # Case-insensitive by name.
    assert [row["name"] for row in body["customers"]] == ["Anjar Farms", "beirut bakery"]
    second = client.get(
        f"/api/v1/tenants/{tenant_id}/customers",
        headers=_auth(token),
        params={"limit": 2, "page": 2},
    ).json()
    assert [row["name"] for row in second["customers"]] == ["Cedar Shop"]
    assert (
        client.get(
            f"/api/v1/tenants/{tenant_id}/customers", headers=_auth(token), params={"limit": 101}
        ).status_code
        == 422
    )
    default = client.get(f"/api/v1/tenants/{tenant_id}/customers", headers=_auth(token)).json()
    assert default["limit"] == 20

    # Another business sees only its own customers.
    _other_owner, other_tenant, other_token = _owner_context(client, session_factory, "custlist2")
    other = client.get(
        f"/api/v1/tenants/{other_tenant}/customers", headers=_auth(other_token)
    ).json()
    assert other["total"] == 0 and other["customers"] == []
    denied = client.get(f"/api/v1/tenants/{tenant_id}/customers", headers=_auth(other_token))
    assert denied.status_code in {403, 404}


def test_invoices_of_a_customer_newest_first_with_current_figures(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "invlist")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    params = {"tenant_id": tenant_id}

    first = client.post(
        "/api/v1/invoices",
        params=params,
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    ).json()
    second = client.post(
        "/api/v1/invoices",
        params=params,
        headers=_auth(token),
        json=_draft_payload(customer["id"], product["id"]),
    ).json()
    # A new draft revision of the second invoice: the list shows the current revision's figures.
    revised = client.put(
        f"/api/v1/invoices/{second['id']}",
        params=params,
        headers=_auth(token),
        json=_draft_payload(
            customer["id"], product["id"], predecessor_id=second["current_revision_id"]
        ),
    )
    assert revised.status_code == 200, revised.text
    # Confirming the first after the second was created puts it first (confirmation date).
    confirmed = client.post(
        f"/api/v1/invoices/{first['id']}/confirm",
        params=params,
        headers=_auth(token),
        json={"expected_revision_id": first["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text

    listed = client.get(
        "/api/v1/invoices",
        params={**params, "customer_id": customer["id"]},
        headers=_auth(token),
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert (body["total"], body["total_pages"]) == (2, 1)
    rows = body["invoices"]
    assert [row["id"] for row in rows] == [first["id"], second["id"]]
    assert rows[0]["status"] == "CONFIRMED"
    assert rows[0]["official_invoice_number"] == confirmed.json()["official_invoice_number"]
    assert rows[0]["total_due"] == confirmed.json()["total_due"]
    assert rows[1]["status"] == "DRAFT"
    assert rows[1]["official_invoice_number"] is None
    assert rows[1]["server_revision_number"] == 2
    assert rows[1]["net_sales"] == revised.json()["net_sales"]
    assert rows[1]["currency"] == "USD"

    paged = client.get(
        "/api/v1/invoices",
        params={**params, "customer_id": customer["id"], "limit": 1, "page": 2},
        headers=_auth(token),
    ).json()
    assert [row["id"] for row in paged["invoices"]] == [second["id"]]

    # A customer with no invoices, an unknown customer, and the customer is required.
    empty_customer = _customer(client, tenant_id, token, "Quiet Customer", "+961 70 111 299")
    empty = client.get(
        "/api/v1/invoices",
        params={**params, "customer_id": empty_customer},
        headers=_auth(token),
    ).json()
    assert empty["total"] == 0 and empty["invoices"] == []
    missing = client.get(
        "/api/v1/invoices",
        params={**params, "customer_id": str(uuid4())},
        headers=_auth(token),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"
    assert client.get("/api/v1/invoices", params=params, headers=_auth(token)).status_code == 422

    # Another business cannot list this customer's invoices through its own context.
    _other_owner, other_tenant, other_token = _owner_context(client, session_factory, "invlist2")
    foreign = client.get(
        "/api/v1/invoices",
        params={"tenant_id": other_tenant, "customer_id": customer["id"]},
        headers=_auth(other_token),
    )
    assert foreign.status_code == 404
