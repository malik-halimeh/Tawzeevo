"""Phase 6 P6-M1: supplier profiles and the append-only price history with derived insights
(PHASE_06.md B/C; D-034, D-059)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from test_invoice_editor import _auth, _catalog, _draft_payload, _owner_context

from tawzeevo_api.models import TenantProductCostEntry, TenantSupplier


def _post(client, tenant, token, path, json):
    return client.post(f"{path}?tenant_id={tenant}", headers=_auth(token), json=json)


def _get(client, tenant, token, path):
    return client.get(f"{path}?tenant_id={tenant}", headers=_auth(token))


def _patch(client, tenant, token, path, json):
    return client.patch(f"{path}?tenant_id={tenant}", headers=_auth(token), json=json)


def _cost(client, tenant, token, product_id, supplier_id, unit_cost, **extra):
    body = {
        "supplier_id": supplier_id,
        "unit_cost": unit_cost,
        "currency": "USD",
        "cost_basis": "PIECE",
        **extra,
    }
    return _post(client, tenant, token, f"/api/v1/suppliers/products/{product_id}/costs", body)


def _at(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def test_supplier_profile_contact_location_version_and_isolation(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "p6prof")
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/suppliers",
        {
            "name": "Bekaa Wholesale",
            "contact_name": "Abu Ali",
            "contact_phone": "03 123 456",
            "address": "Zahle industrial road",
            "latitude": "33.846",
            "longitude": "35.902",
            "notes": "Opens 6am",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["contact_phone"] == "+9613123456"  # normalized like customer phones
    assert body["version"] == 1 and body["latitude"] == "33.846000"

    # Coordinates travel together; a bad phone is refused; unknown fields are refused.
    half = _post(client, tenant, token, "/api/v1/suppliers", {"name": "X", "latitude": "1"})
    assert half.status_code == 422, half.text
    bad = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Y", "contact_phone": "abc"})
    assert bad.status_code == 422
    stock = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Z", "stock": 3})
    assert stock.status_code == 422

    # Partial update bumps the version; a stale expected version is a conflict, not a silent win.
    supplier_id = body["id"]
    path = f"/api/v1/suppliers/{supplier_id}"
    patched = _patch(client, tenant, token, path, {"address": "New depot", "expected_version": 1})
    assert patched.status_code == 200, patched.text
    assert patched.json()["address"] == "New depot" and patched.json()["version"] == 2
    assert patched.json()["contact_name"] == "Abu Ali"  # untouched fields survive
    stale = _patch(client, tenant, token, path, {"notes": "late", "expected_version": 1})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "SUPPLIER_VERSION_CONFLICT"
    cleared = _patch(
        client, tenant, token, path, {"latitude": None, "longitude": None, "contact_phone": ""}
    )
    assert cleared.status_code == 200 and cleared.json()["latitude"] is None
    assert cleared.json()["contact_phone"] is None

    # Another business cannot see or edit it.
    _other, other_tenant, other_token = _owner_context(client, session_factory, "p6prof2")
    assert _get(client, other_tenant, other_token, "/api/v1/suppliers").json() == {"suppliers": []}
    foreign = _patch(client, other_tenant, other_token, path, {"name": "Hijacked"})
    assert foreign.status_code == 404
    with session_factory() as db:
        row = db.get(TenantSupplier, body["id"])
        assert row is not None and row.name == "Bekaa Wholesale" and row.version == 3


def test_price_history_is_append_only_with_provenance_and_derived_insights(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p6hist")
    _category, product, customer = _catalog(client, tenant, token, name="Olive Oil 1L")
    pid = product["id"]
    bekaa = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Bekaa"}).json()["id"]
    north = _post(client, tenant, token, "/api/v1/suppliers", {"name": "North"}).json()["id"]

    # Manual and quote entries append; an owner cannot claim an actual purchase by hand (D-059).
    first = _cost(client, tenant, token, pid, bekaa, "8.0000", effective_at=_at(40))
    assert first.status_code == 201, first.text
    quote = _cost(
        client,
        tenant,
        token,
        pid,
        bekaa,
        "8.4000",
        source_type="QUOTE",
        quantity_context="120",
        effective_at=_at(10),
        notes="for 10 boxes",
    )
    assert quote.status_code == 201, quote.text
    fake = _cost(client, tenant, token, pid, bekaa, "5.0000", source_type="ACTUAL_PURCHASE")
    assert fake.status_code == 422, fake.text
    third = _cost(client, tenant, token, pid, bekaa, "8.2000", effective_at=_at(3))
    assert third.status_code == 201
    # A stale, cheaper competitor and a box-basis entry that must never be compared to pieces.
    stale = _cost(client, tenant, token, pid, north, "7.9000", effective_at=_at(120))
    assert stale.status_code == 201
    box = _cost(
        client,
        tenant,
        token,
        pid,
        north,
        "90.0000",
        cost_basis="BOX",
        pieces_per_box=12,
        effective_at=_at(1),
    )
    assert box.status_code == 201, box.text
    entries = _get(client, tenant, token, f"/api/v1/suppliers/products/{pid}/costs").json()[
        "entries"
    ]
    assert [e["source_type"] for e in entries] == ["MANUAL", "MANUAL", "QUOTE", "MANUAL", "MANUAL"]
    assert entries[2]["quantity_context"] == "120.0000"
    with session_factory() as db:  # the first row is still exactly what was written
        oldest = db.scalar(
            select(TenantProductCostEntry)
            .where(
                TenantProductCostEntry.tenant_product_id == pid,
                TenantProductCostEntry.supplier_id == bekaa,
            )
            .order_by(TenantProductCostEntry.effective_at.asc())
        )
        assert oldest is not None and oldest.unit_cost == Decimal("8.0000")
        assert oldest.source_type == "MANUAL"

    insights = _get(client, tenant, token, f"/api/v1/supplier-prices/products/{pid}")
    assert insights.status_code == 200, insights.text
    body = insights.json()
    assert body["stale_after_days"] == 90
    rows = {(r["supplier_name"], r["cost_basis"]): r for r in body["insights"]}
    assert set(rows) == {("Bekaa", "PIECE"), ("North", "PIECE"), ("North", "BOX")}
    bekaa_piece = rows[("Bekaa", "PIECE")]
    assert bekaa_piece["latest_unit_cost"] == "8.2000"
    assert bekaa_piece["latest_source_type"] == "MANUAL"
    assert bekaa_piece["lowest_unit_cost"] == "8.0000"
    assert bekaa_piece["highest_unit_cost"] == "8.4000"
    assert bekaa_piece["recent_unit_costs"] == ["8.2000", "8.4000", "8.0000"]  # newest first
    assert bekaa_piece["last_purchase_at"] is None and bekaa_piece["entry_count"] == 3
    assert bekaa_piece["stability"] == "STABLE"
    assert Decimal(bekaa_piece["variation_percent"]) < 3
    assert bekaa_piece["is_preferred"] is True  # first cost made Bekaa preferred (D-041)
    north_piece = rows[("North", "PIECE")]
    assert north_piece["age_days"] >= 120  # stale but visible
    assert north_piece["stability"] == "INSUFFICIENT_DATA"
    assert north_piece["variation_percent"] is None
    north_box = rows[("North", "BOX")]
    assert north_box["pieces_per_box"] == 12 and north_box["latest_unit_cost"] == "90.0000"
    # Ordering inside a comparable group is by latest price; groups never mix.
    piece_rows = [r for r in body["insights"] if r["cost_basis"] == "PIECE"]
    assert [r["supplier_name"] for r in piece_rows] == ["North", "Bekaa"]

    # D-059 preload: latest actual purchase > latest quote > manual, for the same basis.
    with session_factory() as db:
        db.add(
            TenantProductCostEntry(
                tenant_id=tenant,
                tenant_product_id=pid,
                supplier_id=bekaa,
                unit_cost=Decimal("7.7500"),
                currency="USD",
                cost_basis="PIECE",
                effective_at=datetime.now(UTC) - timedelta(days=20),
                source_type="ACTUAL_PURCHASE",
                created_by_user_id=owner.id,
            )
        )
        db.commit()
    payload = _draft_payload(customer["id"], pid)
    payload["items"] = [payload["items"][0]]  # type: ignore[index]
    draft = _post(client, tenant, token, "/api/v1/invoices", payload)
    assert draft.status_code == 201, draft.text
    line = draft.json()["items"][0]
    assert line["cost_source_type"] == "ACTUAL_PURCHASE" and line["unit_cost"] == "7.7500"
    assert line["product_cost_entry_id"] not in {e["id"] for e in entries}
    after = _get(client, tenant, token, f"/api/v1/supplier-prices/products/{pid}").json()
    bekaa_after = next(r for r in after["insights"] if r["supplier_name"] == "Bekaa")
    assert bekaa_after["last_purchase_unit_cost"] == "7.7500"
    assert bekaa_after["latest_unit_cost"] == "8.2000"  # latest by date is still the manual one

    # Unknown product or foreign tenant: 404, never a leak.
    missing = _get(client, tenant, token, f"/api/v1/supplier-prices/products/{uuid4()}")
    assert missing.status_code == 404
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p6hist2")
    foreign = _get(client, other_tenant, other_token, f"/api/v1/supplier-prices/products/{pid}")
    assert foreign.status_code == 404


def test_recommendation_is_deterministic_explainable_and_overridable(client, session_factory):
    """PHASE_06.md D: same product, compatible unit/package, same currency, latest price per
    supplier, lowest comparable first, age/source shown, owner override on top (P6-M2)."""
    _owner, tenant, token = _owner_context(client, session_factory, "p6rec")
    _category, product, _customer = _catalog(client, tenant, token, name="Labneh 500g")
    pid = product["id"]
    ids = {}
    for name in ("Bekaa", "North", "South", "Tripoli", "Silent"):
        ids[name] = _post(client, tenant, token, "/api/v1/suppliers", {"name": name}).json()["id"]
    assert (
        _cost(client, tenant, token, pid, ids["Bekaa"], "9.0000", effective_at=_at(30)).status_code
        == 201
    )
    assert (
        _cost(client, tenant, token, pid, ids["Bekaa"], "8.5000", effective_at=_at(2)).status_code
        == 201
    )
    assert (
        _cost(client, tenant, token, pid, ids["North"], "8.5000", effective_at=_at(5)).status_code
        == 201
    )
    assert (
        _cost(client, tenant, token, pid, ids["South"], "7.0000", effective_at=_at(200)).status_code
        == 201
    )
    box = _cost(
        client, tenant, token, pid, ids["Tripoli"], "80.0000", cost_basis="BOX", pieces_per_box=12
    )
    assert box.status_code == 201
    path = f"/api/v1/supplier-prices/products/{pid}/recommendation"

    first = _get(client, tenant, token, path)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["cost_basis"] == "PIECE" and body["currency"] == "USD"
    ranked = [
        (r["rank"], r["supplier_name"], r["unit_cost"], r["explanation"]) for r in body["ranked"]
    ]
    # Same price: the newer entry ranks first; the cheap-but-stale South is ranked last, visible.
    assert ranked == [
        (1, "Bekaa", "8.5000", "LOWEST_COMPARABLE"),
        (2, "North", "8.5000", "SAME_PRICE_OLDER"),
        (3, "South", "7.0000", "STALE_RANKED_LAST"),
    ]
    assert body["ranked"][2]["is_stale"] is True and body["ranked"][2]["age_days"] >= 200
    assert body["ranked"][1]["delta_vs_best"] == "0.0000"
    assert {(e["supplier_name"], e["reason"]) for e in body["excluded"]} == {
        ("Tripoli", "INCOMPATIBLE_UNIT"),
        ("Silent", "NO_PRICE"),
    }
    # Bekaa became preferred with its first cost (D-041), so the owner choice matches.
    assert body["recommended_supplier_id"] == ids["Bekaa"]
    assert body["effective_supplier_id"] == ids["Bekaa"]
    assert body["effective_reason"] == "OWNER_CHOICE_MATCHES_RECOMMENDATION"
    # Reproducible: the same history gives the same answer.
    again = _get(client, tenant, token, path).json()
    assert [r["supplier_id"] for r in again["ranked"]] == [r["supplier_id"] for r in body["ranked"]]

    # The box group is a different comparison; Tripoli ranks alone, piece suppliers are excluded.
    boxes = client.get(
        f"{path}?tenant_id={tenant}&cost_basis=BOX&pieces_per_box=12", headers=_auth(token)
    )
    assert boxes.status_code == 200, boxes.text
    assert [r["supplier_name"] for r in boxes.json()["ranked"]] == ["Tripoli"]
    assert {e["reason"] for e in boxes.json()["excluded"]} == {"INCOMPATIBLE_UNIT", "NO_PRICE"}

    # Owner override with a reason: the recommendation stays visible next to the choice.
    override = client.put(
        f"/api/v1/suppliers/products/{pid}/preferred-supplier?tenant_id={tenant}",
        headers=_auth(token),
        json={"supplier_id": ids["North"], "reason": "delivers on Mondays"},
    )
    assert override.status_code == 200, override.text
    after = _get(client, tenant, token, path).json()
    assert after["recommended_supplier_id"] == ids["Bekaa"]
    assert after["effective_supplier_id"] == ids["North"]
    assert after["effective_reason"] == "OWNER_OVERRIDE"
    with session_factory() as db:
        from tawzeevo_api.models import AuditEvent

        audit = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "preferred_supplier_set", AuditEvent.tenant_id == tenant)
            .order_by(AuditEvent.occurred_at.desc())
        )
        assert audit is not None and audit.details["reason"] == "delivers on Mondays"

    # Isolation: the other business sees nothing of this ranking.
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p6rec2")
    assert _get(client, other_tenant, other_token, path).status_code == 404
