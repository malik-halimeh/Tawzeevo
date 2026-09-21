"""D-078 SLO probe (PHASE_09.md F, P9-M3): measures the accepted targets against a running API
with a disposable database, using the public HTTP surface only.

Targets: phone/barcode lookup p95 < 250 ms; CRUD < 400 ms; storefront checkout < 750 ms;
sync of 100 operations < 2.5 s. Run: `python scripts/slo_probe.py http://127.0.0.1:8011
admin@example.com` (a platform admin must exist to approve the probe tenant). The admin password
is read from TAWZEEVO_ADMIN_PASSWORD or prompted for — never from the command line, so it does
not land in shell history or process lists. Never point this at the hosted database."""

from __future__ import annotations

import getpass
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
ADMIN_EMAIL = sys.argv[2] if len(sys.argv) > 2 else "admin-e2e@example.com"
if len(sys.argv) > 3:
    raise SystemExit(
        "do not pass the admin password on the command line; set TAWZEEVO_ADMIN_PASSWORD"
    )
ADMIN_PASSWORD = os.environ.get("TAWZEEVO_ADMIN_PASSWORD") or getpass.getpass("admin password: ")
SAMPLES = 20
stamp = uuid.uuid4().hex[:6]


def call(method: str, path: str, body=None, token=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
            **(headers or {}),
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} -> {exc.code}: {exc.read()[:300]!r}") from exc
    return payload, (time.perf_counter() - started) * 1000


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * len(ordered))) - 1)]


def main() -> int:
    password = "SloProbePassword123!"
    email = f"slo-{stamp}@example.com"
    call(
        "POST",
        "/register",
        {
            "first_name": "Slo",
            "last_name": "Probe",
            "email": email,
            "phone": f"+96171{int(time.time()) % 1000000:06d}",
            "city": "Beirut",
            "age": 30,
            "password": password,
        },
    )
    token = call("POST", "/login", {"email": email, "password": password})[0]["access_token"]
    admin = call("POST", "/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})[0][
        "access_token"
    ]
    application = call(
        "POST", "/api/v1/tenant-applications", {"business_name": f"SLO {stamp}"}, token
    )[0]
    approved = call(
        "POST", f"/api/v1/platform/tenant-applications/{application['id']}/approve", {}, admin
    )[0]
    tenant = approved.get("tenant_id") or approved["tenant"]["id"]
    category = call(
        "POST",
        f"/api/v1/tenants/{tenant}/categories",
        {"name_en": "Water", "name_ar": "مياه", "slug": f"w-{stamp}"},
        token,
    )[0]
    barcode = f"6299{int(time.time() * 1000) % 10**9:09d}"
    product = call(
        "POST",
        f"/api/v1/tenants/{tenant}/products",
        {
            "category_id": category["id"],
            "name": "Probe Water",
            "barcode": barcode,
            "unit_price": "10.0000",
            "currency": "USD",
            "price_basis": "PIECE",
            "pieces_per_box": 6,
            "is_published": True,
        },
        token,
    )[0]
    slug = f"slo-{stamp}"
    call("PUT", f"/api/v1/tenants/{tenant}/storefront/slug", {"slug": slug}, token)
    phone = f"+96176{int(time.time()) % 1000000:06d}"
    call(
        "POST",
        f"/api/v1/tenants/{tenant}/customers",
        {"name": "Probe Customer", "phone": phone},
        token,
    )
    device = str(uuid.uuid4())
    call(
        "POST",
        f"/api/v1/sync/bootstrap?tenant_id={tenant}",
        {"device_installation_id": device, "protocol_version": 1, "app_schema_version": 1},
        token,
    )

    results: dict[str, tuple[float, float]] = {}

    def measure(label: str, target_ms: float, fn) -> None:
        times = [fn() for _ in range(SAMPLES)]
        results[label] = (p95(times), target_ms)
        verdict = "PASS" if p95(times) < target_ms else "FAIL"
        print(
            f"{label:34s} p50 {statistics.median(times):7.1f} ms  p95 {p95(times):7.1f} ms  "
            f"target < {target_ms:g} ms  {verdict}"
        )

    measure(
        "phone lookup",
        250,
        lambda: call(
            "GET",
            f"/api/v1/tenants/{tenant}/customers/search?phone={urllib.parse.quote(phone)}",
            None,
            token,
        )[1],
    )
    measure(
        "barcode lookup",
        250,
        lambda: call("GET", f"/api/v1/tenants/{tenant}/products/barcode/{barcode}", None, token)[1],
    )
    counter = iter(range(10_000))
    measure(
        "customer create (CRUD)",
        400,
        lambda: call(
            "POST",
            f"/api/v1/tenants/{tenant}/customers",
            {"name": "C", "phone": f"+96170{100000 + next(counter):06d}"},
            token,
        )[1],
    )
    measure(
        "product read (CRUD)",
        400,
        lambda: call("GET", f"/api/v1/tenants/{tenant}/products/{product['id']}", None, token)[1],
    )
    measure(
        "storefront checkout",
        750,
        lambda: call(
            "POST",
            f"/api/v1/public/{slug}/checkout",
            {
                "contact_name": "Guest",
                "contact_phone": f"+96171{200000 + next(counter):06d}",
                "contact_address": "Hamra",
                "items": [{"product_id": product["id"], "quantity": "1", "price_basis": "PIECE"}],
            },
            None,
            {"Idempotency-Key": str(uuid.uuid4())},
        )[1],
    )

    def push_100() -> float:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        operations = [
            {
                "operation_id": str(uuid.uuid4()),
                "entity_type": "customer",
                "operation_type": "create",
                "entity_id": str(uuid.uuid4()),
                "payload": {"name": f"Sync {i}", "phone": f"+96176{500000 + next(counter):06d}"},
                "client_timestamp": now,
            }
            for i in range(100)
        ]
        return call(
            "POST",
            f"/api/v1/sync/push?tenant_id={tenant}",
            {"device_installation_id": device, "protocol_version": 1, "operations": operations},
            token,
        )[1]

    times = [push_100() for _ in range(5)]
    results["sync push 100 operations"] = (max(times), 2500)
    verdict = "PASS" if max(times) < 2500 else "FAIL"
    label = "sync push 100 operations"
    print(f"{label:34s} max {max(times):7.1f} ms (5 runs)  target < 2500 ms  {verdict}")
    failed = [label for label, (value, target) in results.items() if value >= target]
    print("RESULT:", "PASS" if not failed else f"FAIL {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
