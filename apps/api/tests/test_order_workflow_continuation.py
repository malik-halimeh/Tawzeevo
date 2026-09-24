"""Order workflow fix M3: continuing from an order or invoice never changes the financial rules.

Entering Payments from an invoice only preselects that invoice's open obligation in the existing
"choose amounts" allocation; the receipt goes through the same command as the standalone page.
The order detail links its delivery so the owner can stop and resume.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from test_checkout import _cart, _checkout
from test_customer_access import HEADER, _issue
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_storefront import _publish, _slug


def _confirmed_invoice(client, tenant_id, token, customer_id, product_id):
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer_id, product_id),
    )
    assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/invoices/{created.json()['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": created.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def _obligations(client, tenant_id, token, customer_id):
    response = client.get(
        f"/api/v1/payments/customers/{customer_id}/obligations",
        params={"tenant_id": tenant_id, "currency": "USD"},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return {row["source_id"]: row for row in response.json()["obligations"]}


def test_payment_entered_from_the_newer_invoice_settles_exactly_that_invoice(
    client, session_factory
):
    owner, tenant_id, token = _owner_context(client, session_factory, "continue-pay")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    older = _confirmed_invoice(client, tenant_id, token, customer["id"], product["id"])
    newer = _confirmed_invoice(client, tenant_id, token, customer["id"], product["id"])
    before = _obligations(client, tenant_id, token, customer["id"])
    assert set(before) == {older["id"], newer["id"]}
    target = before[newer["id"]]

    # The body the Payments page sends when opened from the newer invoice's next steps: its open
    # amount, allocated by the owner to that obligation (the existing "choose amounts" path).
    receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": target["outstanding_amount"],
            "currency": "USD",
            "method": "CASH",
            "reference": None,
            "paid_at": datetime.now(UTC).isoformat(),
            "allocations": [
                {
                    "target_ledger_entry_id": target["target_ledger_entry_id"],
                    "amount": target["outstanding_amount"],
                }
            ],
        },
    )
    assert receipt.status_code == 201, receipt.text
    body = receipt.json()
    assert body["unallocated_amount"] == "0.0000"
    assert [(row["target_ledger_entry_id"], row["amount"]) for row in body["allocations"]] == [
        (target["target_ledger_entry_id"], target["outstanding_amount"])
    ]
    after = _obligations(client, tenant_id, token, customer["id"])
    assert newer["id"] not in after, "the newer invoice is settled"
    assert after[older["id"]]["outstanding_amount"] == before[older["id"]]["outstanding_amount"]


def test_order_detail_links_its_delivery_and_foreign_invoices_are_not_readable(
    client, session_factory
):
    owner, tenant_id, token = _owner_context(client, session_factory, "continue-del")
    _category, product, customer = _catalog(client, tenant_id, token, name="Cedar Water")
    _publish(client, tenant_id, token, product["id"])
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    slug = _slug(session_factory, tenant_id)
    _link, secret = _issue(client, tenant_id, token, customer["id"])
    placed = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret}).json()
    order_url = f"/api/v1/tenants/{tenant_id}/orders/{placed['order_id']}"
    detail = client.get(order_url, headers=_auth(token)).json()
    assert detail["deliveries"] == []
    confirmed = client.post(
        f"{order_url}/confirm",
        headers=_auth(token),
        json={"expected_revision_id": detail["invoice"]["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    invoice_id = confirmed.json()["invoice"]["id"]
    membership = client.get("/api/v1/tenant-contexts", headers=_auth(token)).json()["tenants"][0]
    task = client.post(
        "/api/v1/delivery-tasks",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "invoice_id": invoice_id,
            "assigned_membership_id": membership["membership_id"],
            "delivery_date": date.today().isoformat(),
        },
    )
    assert task.status_code == 201, task.text
    detail = client.get(order_url, headers=_auth(token)).json()
    assert [(row["id"], row["status"]) for row in detail["deliveries"]] == [
        (task.json()["id"], "ASSIGNED")
    ]

    # Another business cannot open this invoice by id: the prefill link resolves to nothing.
    _other_owner, other_tenant, other_token = _owner_context(client, session_factory, "continue-x")
    foreign = client.get(
        f"/api/v1/invoices/{invoice_id}",
        params={"tenant_id": other_tenant},
        headers=_auth(other_token),
    )
    assert foreign.status_code == 404
