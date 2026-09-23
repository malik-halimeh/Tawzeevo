"""Driver least privilege on the sync snapshot path (PHASE_07.md D/I; D-021; D-031).

Regression for audit finding TWZ-F-001 (rows TWZ-A-042 / TWZ-A-055): a driver device could page
every owner-only snapshot collection although its bootstrap answer advertised none. The snapshot
service now enforces the same per-role allowlist that bootstrap advertises, before any device or
data access.
"""

from __future__ import annotations

from typing import get_args
from uuid import uuid4

from test_delivery_tasks import _driver
from test_fa002_supplier_payment_cap import _opening, _payment_payload
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice
from test_supplier_ledger import _supplier_context
from test_sync_bootstrap import _bootstrap, _page

from tawzeevo_api.models import TenantMembership, TenantRole
from tawzeevo_api.schemas.sync import SnapshotCollection
from tawzeevo_api.services import sync as sync_service

ALL_COLLECTIONS: tuple[str, ...] = get_args(SnapshotCollection)

# Keys that must never reach a driver projection (PHASE_07.md D; D-031).
OWNER_ONLY_KEYS = {
    "unit_cost",
    "cost",
    "latest_cost",
    "cost_snapshot",
    "profit",
    "gross_profit",
    "margin",
    "supplier_id",
    "preferred_supplier_id",
    "net_sales",
    "signed_amount",
    "balance",
}


def _keys(obj, out=None):
    out = out if out is not None else set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.add(str(key))
            _keys(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _keys(value, out)
    return out


def test_snapshot_registry_and_public_collection_type_stay_in_sync():
    """A collection added to the route type must be registered in the service (and vice versa),
    so a future collection cannot bypass the role allowlist by being reachable but unregistered."""
    assert set(sync_service._SNAPSHOT_SOURCES) == set(ALL_COLLECTIONS)


def test_bootstrap_advertises_exactly_the_collections_the_role_may_page():
    owner_membership = TenantMembership(role=TenantRole.OWNER)
    driver_membership = TenantMembership(role=TenantRole.DRIVER)
    assert sync_service.permitted_collections(owner_membership) == list(ALL_COLLECTIONS)
    assert sync_service.permitted_collections(driver_membership) == []


def test_driver_is_refused_every_snapshot_collection_even_with_a_registered_device(
    client, session_factory
):
    owner, tenant, token = _owner_context(client, session_factory, "drv-snap")
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    _user, driver_token, _membership = _driver(
        client, session_factory, tenant, "drv-snap@example.com"
    )
    device = str(uuid4())
    booted = _bootstrap(client, tenant, driver_token, device)
    assert booted.status_code == 200, booted.text
    assert booted.json()["collections"] == []

    for collection in ALL_COLLECTIONS:
        refused = _page(client, tenant, driver_token, device, collection)
        assert refused.status_code == 403, (collection, refused.status_code, refused.text)
        assert refused.json()["detail"]["code"] == "TENANT_OWNER_REQUIRED"
        assert "items" not in refused.json()

    # An unregistered driver device is refused for the same reason: the role check precedes the
    # device lookup, so the answer cannot be used to probe device registration either.
    unregistered = _page(client, tenant, driver_token, str(uuid4()), "customers")
    assert unregistered.status_code == 403
    assert unregistered.json()["detail"]["code"] == "TENANT_OWNER_REQUIRED"

    # The owner projection is unchanged.
    owner_device = str(uuid4())
    assert _bootstrap(client, tenant, token, owner_device).status_code == 200
    for collection in ALL_COLLECTIONS:
        page = _page(client, tenant, token, owner_device, collection)
        assert page.status_code == 200, (collection, page.text)
    customers = _page(client, tenant, token, owner_device, "customers").json()["items"]
    assert customer["id"] in {row["id"] for row in customers}


def test_driver_never_receives_supplier_payment_rows_through_the_snapshot_path(
    client, session_factory
):
    """TWZ-A-055 reconciliation probe: after a supplier payment exists, the payments page is
    closed to a driver (previously 200 with the SUPPLIER_PAYMENT row: amount, supplier_id)."""
    _owner, tenant, token, supplier = _supplier_context(client, session_factory)
    _opening(client, tenant, token, supplier, "USD", "20.0000")
    paid = client.post(
        f"/api/v1/payments/supplier-payments?tenant_id={tenant}",
        headers=_auth(token),
        json=_payment_payload(supplier, "USD", "7.5000"),
    )
    assert paid.status_code == 201, paid.text
    _user, driver_token, _membership = _driver(
        client, session_factory, tenant, "drv-pay@example.com"
    )
    device = str(uuid4())
    assert _bootstrap(client, tenant, driver_token, device).status_code == 200
    refused = _page(client, tenant, driver_token, device, "payments")
    assert refused.status_code == 403, refused.text
    assert "supplier" not in refused.text.lower()

    owner_device = str(uuid4())
    assert _bootstrap(client, tenant, token, owner_device).status_code == 200
    rows = _page(client, tenant, token, owner_device, "payments").json()["items"]
    assert any(row["supplier_id"] == supplier for row in rows)


def test_driver_views_carry_no_owner_only_keys_and_other_roles_are_refused(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "drv-keys")
    _o2, tenant_b, token_b = _owner_context(client, session_factory, "drv-keys-b")
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    _user, driver_token, membership = _driver(
        client, session_factory, tenant, "drv-keys@example.com"
    )
    created = client.post(
        f"/api/v1/delivery-tasks?tenant_id={tenant}",
        headers=_auth(token),
        json={"invoice_id": confirmed["id"], "assigned_membership_id": membership},
    )
    assert created.status_code == 201, created.text
    device = str(uuid4())
    assert _bootstrap(client, tenant, driver_token, device).status_code == 200
    seen: set[str] = set()
    for path in (
        f"/api/v1/delivery-tasks/my-work?tenant_id={tenant}",
        f"/api/v1/sync/pull?tenant_id={tenant}&device_installation_id={device}&cursor=0",
    ):
        response = client.get(path, headers=_auth(driver_token))
        assert response.status_code == 200, (path, response.text)
        seen |= _keys(response.json())
    assert sorted(seen & OWNER_ONLY_KEYS) == []

    # Cross-role / cross-tenant: the other tenant's owner is not a member here; a driver's
    # bearer cannot page the other tenant either.
    owner_device = str(uuid4())
    assert _bootstrap(client, tenant, token, owner_device).status_code == 200
    assert _page(client, tenant, token_b, owner_device, "customers").status_code == 403
    assert _page(client, tenant_b, driver_token, device, "customers").status_code == 403
