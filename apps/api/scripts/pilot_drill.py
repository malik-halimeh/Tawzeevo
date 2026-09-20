"""Multi-tenant pilot drill (PHASE_09.md P9-M7). Runs the two operating models end to end
through the public HTTP API of a target deployment and checks that nothing leaks across
businesses or to a driver:

* Business A — owner + driver: catalog, customer, two confirmed invoices, receipt, procurement
  list from demand, supplier purchase, delivery task assigned to the driver, driver completes
  it, driver sync bootstrap carries nothing owner-only, analytics reconcile.
* Business B — one owner, zero drivers: same flow with the owner as the only operator.
* Cross-checks — owner B cannot read A (analytics, customers, branding), the driver of A cannot
  read A's supplier prices or B's anything, the platform admin reads no tenant-private data.

Usage: python scripts/pilot_drill.py <api_url> <admin_email> <admin_password>
       [--owner-a email] [--driver-a email] [--owner-b email] [--password value]
Never point this at the production database from a test; on staging it is the rehearsal.
Prints one line per check and a final PASS/FAIL; exit code 1 on any failure."""

from __future__ import annotations

import argparse
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, date, datetime, timedelta

CHECKS: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}{'  — ' + detail if detail else ''}")


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body=None, token=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {token}"} if token else {}),
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except Exception:
                return exc.code, {"raw": raw[:200].decode(errors="replace")}


def ensure_user(api: Api, email: str, password: str, first: str, last: str, phone: str) -> str:
    status, body = api.call("POST", "/login", {"email": email, "password": password})
    if status == 200:
        return body["access_token"]
    status, body = api.call(
        "POST",
        "/register",
        {
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": phone,
            "city": "Beirut",
            "age": 30,
            "password": password,
        },
    )
    if status not in (201, 409):
        raise SystemExit(f"register {email} -> {status} {body}")
    status, body = api.call("POST", "/login", {"email": email, "password": password})
    if status != 200:
        raise SystemExit(
            f"login {email} -> {status} {body} (existing account with another password?)"
        )
    return body["access_token"]


def phone_for(seed: int) -> str:
    return f"+96170{(int(time.time()) + seed) % 1_000_000:06d}"


def business(api: Api, token: str, admin_token: str, name: str) -> str:
    status, app = api.call("POST", "/api/v1/tenant-applications", {"business_name": name}, token)
    if status != 201:
        raise SystemExit(f"application -> {status} {app}")
    status, approved = api.call(
        "POST", f"/api/v1/platform/tenant-applications/{app['id']}/approve", {}, admin_token
    )
    if status != 200:
        raise SystemExit(f"approve -> {status} {approved}")
    return approved.get("tenant_id") or approved["tenant"]["id"]


def run_business(
    api: Api, owner: str, admin: str, name: str, driver_email: str | None
) -> dict[str, object]:
    tenant = business(api, owner, admin, name)
    q = f"?tenant_id={tenant}"
    stamp = uuid.uuid4().hex[:6]
    _, category = api.call(
        "POST",
        f"/api/v1/tenants/{tenant}/categories",
        {"name_en": "Water", "name_ar": "مياه", "slug": f"water-{stamp}"},
        owner,
    )
    _, product = api.call(
        "POST",
        f"/api/v1/tenants/{tenant}/products",
        {
            "category_id": category["id"],
            "name": f"Pilot Water {stamp}",
            "barcode": f"6298{int(time.time() * 1000) % 10**9:09d}",
            "unit_price": "10.0000",
            "currency": "USD",
            "price_basis": "PIECE",
            "pieces_per_box": 6,
            "is_published": True,
        },
        owner,
    )
    _, supplier = api.call("POST", f"/api/v1/suppliers{q}", {"name": f"Source {stamp}"}, owner)
    api.call(
        "POST",
        f"/api/v1/suppliers/products/{product['id']}/costs{q}",
        {
            "supplier_id": supplier["id"],
            "unit_cost": "7.0000",
            "currency": "USD",
            "cost_basis": "PIECE",
        },
        owner,
    )
    _, customer = api.call(
        "POST",
        f"/api/v1/tenants/{tenant}/customers",
        {"name": f"Pilot Customer {stamp}", "phone": phone_for(11), "address": "Hamra"},
        owner,
    )
    invoices = []
    for qty in ("2", "3"):
        _, draft = api.call(
            "POST",
            f"/api/v1/invoices{q}",
            {
                "client_command_id": str(uuid.uuid4()),
                "customer_id": customer["id"],
                "currency": "USD",
                "invoice_discount_expression": "0",
                "invoice_markup_expression": "0",
                "items": [
                    {
                        "product_id": product["id"],
                        "quantity_expression": qty,
                        "price_basis": "PIECE",
                        "line_discount_expression": "0",
                        "line_markup_expression": "0",
                    }
                ],
            },
            owner,
        )
        status, confirmed = api.call(
            "POST",
            f"/api/v1/invoices/{draft['id']}/confirm{q}",
            {"expected_revision_id": draft["current_revision_id"]},
            owner,
        )
        check(
            f"{name}: invoice confirmed",
            status == 200,
            str(confirmed.get("official_invoice_number")),
        )
        invoices.append(confirmed)
    status, receipt = api.call(
        "POST",
        f"/api/v1/payments/customer-receipts{q}",
        {
            "idempotency_key": str(uuid.uuid4()),
            "customer_id": customer["id"],
            "amount": "15.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
        owner,
    )
    check(f"{name}: receipt recorded", status == 201, str(receipt.get("customer_balance", status)))
    today = date.today()
    status, plist = api.call(
        "POST",
        f"/api/v1/procurement/lists{q}",
        {"demand_from": (today - timedelta(days=1)).isoformat(), "demand_to": today.isoformat()},
        owner,
    )
    check(
        f"{name}: procurement list from demand", status == 201 and plist.get("items"), str(status)
    )
    status, purchase = api.call(
        "POST",
        f"/api/v1/supplier-purchases{q}",
        {
            "idempotency_key": str(uuid.uuid4()),
            "supplier_id": supplier["id"],
            "currency": "USD",
            "procurement_list_id": plist.get("id"),
            "items": [{"product_id": product["id"], "quantity": "5", "unit_cost": "7.0000"}],
        },
        owner,
    )
    check(f"{name}: supplier purchase", status == 201, str(purchase.get("total_amount")))

    membership_id = None
    if driver_email:
        status, member = api.call(
            "POST", f"/api/v1/tenants/{tenant}/memberships", {"email": driver_email}, owner
        )
        check(f"{name}: driver added", status in (200, 201), str(member.get("role", member)))
        membership_id = member.get("id")
    status, task = api.call(
        "POST",
        f"/api/v1/delivery-tasks{q}",
        {
            "invoice_id": invoices[0]["id"],
            **({"assigned_membership_id": membership_id} if membership_id else {}),
        },
        owner,
    )
    check(f"{name}: delivery task created", status == 201, str(task.get("status")))
    return {
        "tenant": tenant,
        "customer": customer,
        "product": product,
        "task": task,
        "invoices": invoices,
        "supplier": supplier,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("api_url")
    parser.add_argument("admin_email")
    parser.add_argument("admin_password")
    parser.add_argument("--owner-a", default=None)
    parser.add_argument("--driver-a", default=None)
    parser.add_argument("--owner-b", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()
    api = Api(args.api_url)
    stamp = uuid.uuid4().hex[:6]
    password = args.password or ("Pilot-" + secrets.token_urlsafe(12))
    owner_a_email = args.owner_a or f"pilot-owner-a-{stamp}@example.com"
    driver_a_email = args.driver_a or f"pilot-driver-a-{stamp}@example.com"
    owner_b_email = args.owner_b or f"pilot-owner-b-{stamp}@example.com"
    if not args.password:
        print(f"generated password for pilot accounts: {password}")

    status, body = api.call(
        "POST", "/login", {"email": args.admin_email, "password": args.admin_password}
    )
    if status != 200:
        raise SystemExit(f"admin login failed: {status} {body}")
    admin = body["access_token"]
    owner_a = ensure_user(api, owner_a_email, password, "Pilot", "OwnerA", phone_for(1))
    driver_a = ensure_user(api, driver_a_email, password, "Pilot", "DriverA", phone_for(2))
    owner_b = ensure_user(api, owner_b_email, password, "Pilot", "OwnerB", phone_for(3))

    a = run_business(api, owner_a, admin, f"Pilot Van A {stamp}", driver_a_email)
    b = run_business(api, owner_b, admin, f"Pilot Van B {stamp}", None)
    ta, tb = a["tenant"], b["tenant"]

    # Driver of A: least privilege, offline-style completion through sync, nothing owner-only.
    status, my_work = api.call(
        "GET", f"/api/v1/delivery-tasks/my-work?tenant_id={ta}", None, driver_a
    )
    check(
        "driver A sees exactly one assigned stop",
        status == 200 and len(my_work.get("tasks", [])) == 1,
        str(status),
    )
    text = json.dumps(my_work)
    check(
        "driver A payload has no cost/profit/supplier price",
        not any(w in text for w in ("unit_cost", "profit", "margin")),
    )
    status, _ = api.call("GET", f"/api/v1/suppliers?tenant_id={ta}", None, driver_a)
    check("driver A cannot read supplier desk", status == 403, str(status))
    status, boot = api.call(
        "POST",
        f"/api/v1/sync/bootstrap?tenant_id={ta}",
        {
            "device_installation_id": str(uuid.uuid4()),
            "protocol_version": 1,
            "app_schema_version": 1,
        },
        driver_a,
    )
    check(
        "driver A bootstrap carries no owner collections",
        status == 200 and not boot.get("collections"),
        str(boot.get("collections")),
    )
    task = my_work["tasks"][0] if my_work.get("tasks") else {}
    status, done = api.call(
        "POST",
        f"/api/v1/delivery-tasks/{task.get('id')}/complete?tenant_id={ta}",
        {"expected_version": task.get("version", 1)},
        driver_a,
    )
    check(
        "driver A completes the assigned stop",
        status == 200 and done.get("status") == "COMPLETED",
        str(status),
    )

    # Owner B alone: completes their own delivery.
    tb_task = b["task"]
    status, done_b = api.call(
        "POST",
        f"/api/v1/delivery-tasks/{tb_task.get('id')}/complete?tenant_id={tb}",
        {"expected_version": tb_task.get("version", 1)},
        owner_b,
    )
    check(
        "owner B (no driver) completes own delivery",
        status == 200 and done_b.get("status") == "COMPLETED",
        str(status),
    )

    # Analytics reconcile for both.
    for label, tenant, token in (("A", ta, owner_a), ("B", tb, owner_b)):
        status, overview = api.call(
            "GET", f"/api/v1/analytics/overview?tenant_id={tenant}&period=30d", None, token
        )
        usd = (
            {r["currency"]: r["amount"] for r in overview.get("invoiced_sales", [])}
            if status == 200
            else {}
        )
        out = (
            {r["currency"]: r["amount"] for r in overview.get("customer_outstanding", [])}
            if status == 200
            else {}
        )
        pay = (
            {r["currency"]: r["amount"] for r in overview.get("supplier_payable", [])}
            if status == 200
            else {}
        )
        check(
            f"analytics {label} reconcile (50 invoiced, 35 outstanding, 35 payable)",
            usd.get("USD") == "50.0000"
            and out.get("USD") == "35.0000"
            and pay.get("USD") == "35.0000",
            f"{usd} {out} {pay}",
        )

    # Cross-tenant and admin boundaries.
    for label, method, path, token, expected in (
        (
            "owner B cannot read A analytics",
            "GET",
            f"/api/v1/analytics/overview?tenant_id={ta}",
            owner_b,
            403,
        ),
        ("owner B cannot read A branding", "GET", f"/api/v1/tenants/{ta}/branding", owner_b, 403),
        (
            "owner B cannot search A customers",
            "GET",
            f"/api/v1/tenants/{ta}/customers/search?phone=%2B96170123456",
            owner_b,
            403,
        ),
        (
            "driver A cannot read B my-work",
            "GET",
            f"/api/v1/delivery-tasks/my-work?tenant_id={tb}",
            driver_a,
            403,
        ),
        (
            "admin reads no tenant analytics",
            "GET",
            f"/api/v1/analytics/overview?tenant_id={ta}",
            admin,
            403,
        ),
        (
            "admin reads no tenant customers",
            "GET",
            f"/api/v1/tenants/{ta}/customers/search?phone=%2B96170123456",
            admin,
            403,
        ),
        (
            "anonymous reads nothing private",
            "GET",
            f"/api/v1/analytics/overview?tenant_id={ta}",
            None,
            401,
        ),
    ):
        status, body = api.call(method, path, None, token)
        leaked = ta in json.dumps(body) and status >= 300
        check(label, status == expected and not leaked, str(status))

    # Public storefront of both businesses is reachable and price-only.
    for label, tenant, token in (("A", ta, owner_a), ("B", tb, owner_b)):
        status, settings = api.call(
            "GET", f"/api/v1/tenants/{tenant}/storefront?tenant_id={tenant}", None, token
        )
        slug = settings.get("slug") if status == 200 else None
        status, catalog = api.call("GET", f"/api/v1/public/{slug}/catalog/products")
        text = json.dumps(catalog)
        check(
            f"storefront {label} public catalog without private words",
            status == 200 and not any(w in text for w in ("cost", "grade", "debt", "supplier")),
            str(status),
        )

    failed = [c for c in CHECKS if not c[1]]
    verdict = "PASS" if not failed else "FAIL"
    print()
    print(f"RESULT: {verdict} ({len(CHECKS) - len(failed)}/{len(CHECKS)} checks)")
    print(f"accounts: owner A {owner_a_email}, driver A {driver_a_email}, owner B {owner_b_email}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
