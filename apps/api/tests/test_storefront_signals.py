"""P5-M2: interactions, deterministic recommendations, featured campaigns (D-048, D-051, D-062)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_storefront import _publish, _slug

from tawzeevo_api.models import ProductInteraction, ProductInteractionRollup
from tawzeevo_api.services import storefront_signals


def _product(client, tenant, token, category_id, name, barcode, published=True):
    created = client.post(
        f"/api/v1/tenants/{tenant}/products",
        headers=_auth(token),
        json={
            "category_id": category_id,
            "name": name,
            "barcode": barcode,
            "unit_price": "2.0000",
            "currency": "USD",
            "price_basis": "PIECE",
            "is_published": published,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _view(client, slug, product_id, session):
    return client.post(
        f"/api/v1/public/{slug}/catalog/products/{product_id}/view",
        json={"session_id": session},
    )


def _confirm_sale(client, session_factory, owner, tenant, token, customer_id, product):
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    payload = _confirmable_payload(customer_id, product["id"])
    payload["items"][0]["barcode"] = product["barcode"]  # type: ignore[index]
    draft = client.post(
        f"/api/v1/invoices?tenant_id={tenant}",
        headers=_auth(token),
        json=payload,
    )
    assert draft.status_code == 201, draft.text
    confirmed = client.post(
        f"/api/v1/invoices/{draft.json()['id']}/confirm?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_revision_id": draft.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def test_purchase_outweighs_views_dedupe_and_cancelled_sale_is_excluded(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "signals")
    category, cedar, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, cedar["id"])
    labneh = _product(client, tenant, token, category["id"], "Labneh", "5280000000101")
    bread = _product(client, tenant, token, category["id"], "Bread", "5280000000102")
    hidden = _product(client, tenant, token, category["id"], "Hidden", "5280000000103", False)
    slug = _slug(session_factory, tenant)

    # Nothing yet: no recommendations rather than an arbitrary list.
    assert client.get(f"/api/v1/public/{slug}/catalog/recommended").json()["items"] == []

    # Nine views of bread from nine sessions; the same session viewing twice counts once (D-062).
    for index in range(9):
        assert _view(client, slug, bread["id"], f"session-{index:02d}").json()["counted"] is True
    assert _view(client, slug, bread["id"], "session-00").json()["counted"] is False
    assert _view(client, slug, hidden["id"], "session-00").status_code == 404
    assert _view(client, slug, bread["id"], "short").status_code == 422
    # One valid purchase of labneh (weight 10) beats nine views (weight 9).
    _confirm_sale(client, session_factory, owner, tenant, token, customer["id"], labneh)
    ranked = client.get(f"/api/v1/public/{slug}/catalog/recommended").json()["items"]
    assert [row["name"] for row in ranked] == ["Labneh", "Bread"]
    scores = storefront_signals.product_scores  # exercised through a session below
    with session_factory() as db:
        table = scores(db, UUID(tenant))
        assert table[UUID(labneh["id"])].score == 10 and table[UUID(bread["id"])].score == 9
        assert UUID(hidden["id"]) not in table
        stored = db.scalar(select(ProductInteraction.session_key))
        assert stored and "session" not in stored, "session ids are stored hashed only"

    # A cancelled sale no longer counts; a tenth view then puts bread ahead.
    sale = _confirm_sale(client, session_factory, owner, tenant, token, customer["id"], cedar)
    ranked = client.get(f"/api/v1/public/{slug}/catalog/recommended").json()["items"]
    assert [row["name"] for row in ranked][:2] == ["Cedar Water", "Labneh"]  # tie: name order
    cancelled = client.post(
        f"/api/v1/invoices/{sale['id']}/cancel?tenant_id={tenant}",
        headers=_auth(token),
        json={"reason": "Customer withdrew", "idempotency_key": str(uuid4())},
    )
    assert cancelled.status_code == 200, cancelled.text
    ranked = client.get(f"/api/v1/public/{slug}/catalog/recommended").json()["items"]
    assert [row["name"] for row in ranked] == ["Labneh", "Bread"]
    assert _view(client, slug, bread["id"], "session-09").json()["counted"] is True
    assert _view(client, slug, bread["id"], "session-10").json()["counted"] is True
    ranked = client.get(f"/api/v1/public/{slug}/catalog/recommended").json()["items"]
    assert [row["name"] for row in ranked] == ["Bread", "Labneh"]
    limited = client.get(f"/api/v1/public/{slug}/catalog/recommended", params={"limit": 1}).json()
    assert [row["name"] for row in limited["items"]] == ["Bread"]

    # Another business sees nothing of these signals.
    _other, other_tenant, other_token = _owner_context(client, session_factory, "signals-b")
    other_cat, other_product, _c = _catalog(client, other_tenant, other_token, name="Other")
    _publish(client, other_tenant, other_token, other_product["id"])
    other_slug = _slug(session_factory, other_tenant)
    assert client.get(f"/api/v1/public/{other_slug}/catalog/recommended").json()["items"] == []
    assert _view(client, other_slug, bread["id"], "session-x1").status_code == 404


def test_featured_campaigns_interval_tiebreak_and_isolation(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "featured")
    category, cedar, _customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, cedar["id"])
    labneh = _product(client, tenant, token, category["id"], "Labneh", "5280000000201")
    bread = _product(client, tenant, token, category["id"], "Bread", "5280000000202")
    hidden = _product(client, tenant, token, category["id"], "Hidden", "5280000000203", False)
    slug = _slug(session_factory, tenant)
    path = f"/api/v1/tenants/{tenant}/storefront/campaigns"
    now = datetime.now(UTC)

    created = client.post(path, headers=_auth(token), json={"product_id": cedar["id"]})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["active"] is True and body["priority"] == 0
    starts = datetime.fromisoformat(body["starts_at"])
    ends = datetime.fromisoformat(body["ends_at"])
    assert ends - starts == timedelta(days=7), "default campaign length is seven days"

    # Same priority: the newer campaign wins; a higher priority wins regardless of age.
    client.post(path, headers=_auth(token), json={"product_id": bread["id"]})
    client.post(path, headers=_auth(token), json={"product_id": labneh["id"], "priority": 5})
    featured = client.get(f"/api/v1/public/{slug}/catalog/featured").json()["items"]
    assert [row["name"] for row in featured] == ["Labneh", "Bread", "Cedar Water"]

    # Future and expired windows are not active; the records stay.
    future = client.post(
        path,
        headers=_auth(token),
        json={
            "product_id": cedar["id"],
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "priority": 9,
        },
    )
    assert future.status_code == 201 and future.json()["active"] is False
    expired = client.post(
        path,
        headers=_auth(token),
        json={
            "product_id": cedar["id"],
            "starts_at": (now - timedelta(days=9)).isoformat(),
            "ends_at": (now - timedelta(days=2)).isoformat(),
            "priority": 9,
        },
    )
    assert expired.status_code == 201 and expired.json()["active"] is False
    assert [
        row["name"] for row in client.get(f"/api/v1/public/{slug}/catalog/featured").json()["items"]
    ][0] == "Labneh"
    backwards = client.post(
        path,
        headers=_auth(token),
        json={
            "product_id": cedar["id"],
            "starts_at": now.isoformat(),
            "ends_at": (now - timedelta(hours=1)).isoformat(),
        },
    )
    assert backwards.status_code == 422

    # An unpublished product can be scheduled but is never shown until published.
    assert (
        client.post(
            path, headers=_auth(token), json={"product_id": hidden["id"], "priority": 50}
        ).status_code
        == 201
    )
    assert "Hidden" not in client.get(f"/api/v1/public/{slug}/catalog/featured").text
    _publish(client, tenant, token, hidden["id"])
    assert (
        client.get(f"/api/v1/public/{slug}/catalog/featured").json()["items"][0]["name"] == "Hidden"
    )

    # Cancelling removes it from the storefront; the record is retained and listed.
    cancel_id = client.get(path, headers=_auth(token)).json()["campaigns"]
    hidden_campaign = next(row for row in cancel_id if row["tenant_product_id"] == hidden["id"])
    assert (
        client.post(f"{path}/{hidden_campaign['id']}/cancel", headers=_auth(token)).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/public/{slug}/catalog/featured").json()["items"][0]["name"] == "Labneh"
    )
    listed = client.get(path, headers=_auth(token)).json()["campaigns"]
    assert len(listed) == 6 and sum(1 for row in listed if row["cancelled_at"]) == 1

    # Never another business's product; another owner cannot touch these campaigns.
    _other, other_tenant, other_token = _owner_context(client, session_factory, "featured-b")
    foreign = client.post(
        f"/api/v1/tenants/{other_tenant}/storefront/campaigns",
        headers=_auth(other_token),
        json={"product_id": cedar["id"]},
    )
    assert foreign.status_code == 404
    assert client.get(path, headers=_auth(other_token)).status_code == 403


def test_raw_views_roll_up_into_monthly_counts_after_ninety_days(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "rollup")
    _category, cedar, _customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, cedar["id"])
    long_ago = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    with session_factory() as db:
        for index in range(4):
            storefront_signals.record_view(
                db,
                UUID(tenant),
                UUID(cedar["id"]),
                f"old-session-{index}",
                long_ago + timedelta(hours=index),
            )
        storefront_signals.record_view(
            db, UUID(tenant), UUID(cedar["id"]), "fresh-session", datetime.now(UTC)
        )
        assert db.scalar(select(func.count()).select_from(ProductInteraction)) == 5
        assert storefront_signals.product_scores(db, UUID(tenant))[UUID(cedar["id"])].views == 5

        folded = storefront_signals.rollup_views(db, datetime(2026, 9, 18, tzinfo=UTC))
        assert folded == 4
        assert db.scalar(select(func.count()).select_from(ProductInteraction)) == 1
        rollup = db.scalar(select(ProductInteractionRollup))
        assert rollup is not None and rollup.views == 4 and rollup.month.isoformat() == "2026-05-01"
        # Rolled-up views still count; running the job again folds nothing.
        assert storefront_signals.product_scores(db, UUID(tenant))[UUID(cedar["id"])].views == 5
        assert storefront_signals.rollup_views(db, datetime(2026, 9, 18, tzinfo=UTC)) == 0
