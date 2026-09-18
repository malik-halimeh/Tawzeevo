"""P5-M1: public storefront routing and published catalog (PHASE_05.md A/B/C/O; D-047)."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import select
from test_invoice_editor import _auth, _catalog, _login, _owner_context, _user

from tawzeevo_api.models import (
    AuditEvent,
    MasterCategory,
    MasterProduct,
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantSlugRedirect,
)
from tawzeevo_api.routes.cash_van import _storage_dependency
from tawzeevo_api.services.media import LocalObjectStorage
from tawzeevo_api.services.storefront import RESERVED_SLUGS


def _slug(session_factory, tenant):
    with session_factory() as db:
        row = db.get(Tenant, UUID(tenant))
        assert row is not None
        return row.slug


def _publish(client, tenant, token, product_id, published=True, **extra):
    response = client.put(
        f"/api/v1/tenants/{tenant}/products/{product_id}",
        headers=_auth(token),
        json={"is_published": published, **extra},
    )
    assert response.status_code == 200, response.text


def test_catalog_shows_only_published_tenant_products_at_public_prices(
    client, session_factory, tmp_path
):
    owner_a, tenant_a, token_a = _owner_context(client, session_factory, "store-a")
    _owner_b, tenant_b, token_b = _owner_context(client, session_factory, "store-b")
    _category_a, product_a, _customer_a = _catalog(
        client, tenant_a, token_a, name="Cedar Water", barcode="5280000000012"
    )
    _category_b, product_b, _customer_b = _catalog(
        client, tenant_b, token_b, name="Bekaa Olive Oil", barcode="5280000000029"
    )
    slug_a = _slug(session_factory, tenant_a)
    assert slug_a.startswith("route-store-a"), slug_a

    # Unpublished: the storefront exists but shows nothing.
    empty = client.get(f"/api/v1/public/{slug_a}/catalog")
    assert empty.status_code == 200, empty.text
    assert empty.json()["published_products"] == 0 and empty.json()["categories"] == []
    assert empty.json()["accepting_orders"] is True
    assert empty.headers["cache-control"].startswith("public")
    hidden = client.get(f"/api/v1/public/{slug_a}/catalog/products/{product_a['id']}")
    assert hidden.status_code == 404

    # A master product existing globally never appears on its own.
    with session_factory() as db:
        master_category = MasterCategory(name_en="Global", name_ar="عالمي")
        db.add(master_category)
        db.flush()
        db.add(MasterProduct(master_category_id=master_category.id, name="Global Only Product"))
        db.commit()

    _publish(client, tenant_a, token_a, product_a["id"], name_ar="مياه الأرز")
    _publish(client, tenant_b, token_b, product_b["id"])
    # An explicit grade price for tenant A must never reach the public price.
    grade = client.put(
        f"/api/v1/tenants/{tenant_a}/products/{product_a['id']}/grade-prices/A",
        headers=_auth(token_a),
        json={"unit_price": "9.0000"},
    )
    assert grade.status_code in (200, 201, 404), grade.text

    storage = LocalObjectStorage(tmp_path / "objects")
    from tawzeevo_api.main import app

    app.dependency_overrides[_storage_dependency] = lambda: storage
    try:
        source = BytesIO()
        Image.new("RGB", (12, 8), (200, 30, 30)).save(source, format="PNG")
        uploaded = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product_a['id']}/images",
            headers=_auth(token_a),
            files={"file": ("water.png", source.getvalue(), "image/png")},
            data={"alt_text": "Bottle"},
        )
        assert uploaded.status_code == 201, uploaded.text

        card = client.get(f"/api/v1/public/{slug_a}/catalog").json()
        assert card["published_products"] == 1
        assert [c["product_count"] for c in card["categories"]] == [1]
        listing = client.get(f"/api/v1/public/{slug_a}/catalog/products")
        assert listing.status_code == 200, listing.text
        items = listing.json()["items"]
        assert [item["name"] for item in items] == ["Cedar Water"]
        item = items[0]
        assert item["name_ar"] == "مياه الأرز"
        assert item["barcode"] == "5280000000012"
        assert item["price"] == product_a["unit_price"] and item["currency"] == "USD"
        assert item["packaging"]["piece_price"] == product_a["piece_price"]
        assert item["images"][0]["alt_text"] == "Bottle"
        image = client.get(item["images"][0]["url"])
        assert image.status_code == 200 and image.headers["content-type"] == "image/webp"
        # No stock, availability, grade, cost or supplier words anywhere in the public payload.
        body = listing.text.lower()
        for forbidden in ("stock", "availab", "quantity_on_hand", "grade", "cost", "supplier"):
            assert forbidden not in body, forbidden
        # Tenant B's product is absent from A, and A's from B.
        assert "Bekaa Olive Oil" not in listing.text
        slug_b = _slug(session_factory, tenant_b)
        other = client.get(f"/api/v1/public/{slug_b}/catalog/products").json()["items"]
        assert [row["name"] for row in other] == ["Bekaa Olive Oil"]
        assert (
            client.get(f"/api/v1/public/{slug_b}/catalog/products/{product_a['id']}").status_code
            == 404
        )
        image_path = item["images"][0]["url"].removeprefix(f"/api/v1/public/{slug_a}")
        assert client.get(f"/api/v1/public/{slug_b}{image_path}").status_code == 404
        assert (
            "Global Only Product"
            not in client.get(f"/api/v1/public/{slug_a}/catalog/products").text
        )

        # Hiding the product removes it from the storefront immediately.
        _publish(client, tenant_a, token_a, product_a["id"], published=False)
        assert client.get(f"/api/v1/public/{slug_a}/catalog/products").json()["total"] == 0
        assert client.get(item["images"][0]["url"]).status_code == 404
    finally:
        app.dependency_overrides.pop(_storage_dependency, None)


def test_search_is_deterministic_exact_then_prefix_then_contains_and_paginated(
    client, session_factory
):
    _owner, tenant, token = _owner_context(client, session_factory, "store-search")
    category, first, _customer = _catalog(
        client, tenant, token, name="Water Cedar", barcode="5280000000036"
    )
    slug = _slug(session_factory, tenant)
    names = ["Cedar Water", "Cedar Sparkling", "Alpine Cedar Tea", "Bread"]
    ids = {}
    for index, name in enumerate(names):
        created = client.post(
            f"/api/v1/tenants/{tenant}/products",
            headers=_auth(token),
            json={
                "category_id": category["id"],
                "name": name,
                "barcode": f"52800000001{index:02d}",
                "unit_price": "1.0000",
                "currency": "USD",
                "price_basis": "PIECE",
                "is_published": True,
            },
        )
        assert created.status_code == 201, created.text
        ids[name] = created.json()["id"]
    _publish(client, tenant, token, first["id"])

    hits = client.get(f"/api/v1/public/{slug}/catalog/products", params={"query": "cedar"}).json()
    assert [row["name"] for row in hits["items"]] == [
        "Cedar Sparkling",  # prefix matches, alphabetical
        "Cedar Water",
        "Alpine Cedar Tea",  # contains
        "Water Cedar",
    ]
    exact = client.get(
        f"/api/v1/public/{slug}/catalog/products", params={"query": "Cedar Water"}
    ).json()
    assert exact["items"][0]["name"] == "Cedar Water"
    by_barcode = client.get(
        f"/api/v1/public/{slug}/catalog/products", params={"query": "5280000000036"}
    ).json()
    assert [row["name"] for row in by_barcode["items"]] == ["Water Cedar"]
    page_one = client.get(f"/api/v1/public/{slug}/catalog/products", params={"page_size": 2}).json()
    page_two = client.get(
        f"/api/v1/public/{slug}/catalog/products", params={"page_size": 2, "page": 2}
    ).json()
    page_three = client.get(
        f"/api/v1/public/{slug}/catalog/products", params={"page_size": 2, "page": 3}
    ).json()
    assert page_one["total"] == 5 and page_one["has_more"] is True
    assert [row["name"] for row in page_one["items"]] == ["Alpine Cedar Tea", "Bread"]
    assert [row["name"] for row in page_two["items"]] == ["Cedar Sparkling", "Cedar Water"]
    assert [row["name"] for row in page_three["items"]] == ["Water Cedar"] and page_three[
        "has_more"
    ] is False
    filtered = client.get(
        f"/api/v1/public/{slug}/catalog/products",
        params={"category_id": category["id"], "page_size": 60},
    ).json()
    assert filtered["total"] == 5
    assert (
        client.get(f"/api/v1/public/{slug}/catalog/products", params={"page_size": 999}).status_code
        == 422
    )


def test_slug_rename_redirects_is_audited_and_is_never_authorization(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "store-slug")
    _other_owner, other_tenant, other_token = _owner_context(
        client, session_factory, "store-slug-b"
    )
    slug = _slug(session_factory, tenant)

    settings = client.get(f"/api/v1/tenants/{tenant}/storefront", headers=_auth(token))
    assert settings.status_code == 200 and settings.json()["slug"] == slug
    assert settings.json()["previous_slugs"] == []

    for bad in ("ab", "Has Space", "-lead", "api", "workspace"):
        refused = client.put(
            f"/api/v1/tenants/{tenant}/storefront/slug", headers=_auth(token), json={"slug": bad}
        )
        assert refused.status_code in (409, 422), (bad, refused.text)
    taken = client.put(
        f"/api/v1/tenants/{tenant}/storefront/slug",
        headers=_auth(token),
        json={"slug": _slug(session_factory, other_tenant)},
    )
    assert taken.status_code == 409 and taken.json()["detail"]["code"] == "SLUG_TAKEN"

    renamed = client.put(
        f"/api/v1/tenants/{tenant}/storefront/slug",
        headers=_auth(token),
        json={"slug": "cedar-van"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["slug"] == "cedar-van" and renamed.json()["previous_slugs"] == [slug]
    # The old address redirects; the new one is canonical.
    old = client.get(f"/api/v1/public/{slug}/catalog")
    assert old.status_code == 200 and old.json()["redirected_from"] == slug
    assert old.json()["slug"] == "cedar-van"
    new = client.get("/api/v1/public/cedar-van/catalog").json()
    assert new["redirected_from"] is None
    # Nobody else can take the old address while it redirects.
    squat = client.put(
        f"/api/v1/tenants/{other_tenant}/storefront/slug",
        headers=_auth(other_token),
        json={"slug": slug},
    )
    assert squat.status_code == 409
    with session_factory() as db:
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "STOREFRONT_SLUG_RENAMED"))
        assert audit is not None and audit.details == {"from": slug, "to": "cedar-van"}
        assert (
            db.scalar(select(TenantSlugRedirect).where(TenantSlugRedirect.slug == slug)) is not None
        )
    # Going back to the earlier address swaps the redirect.
    back = client.put(
        f"/api/v1/tenants/{tenant}/storefront/slug", headers=_auth(token), json={"slug": slug}
    )
    assert back.status_code == 200 and back.json()["previous_slugs"] == ["cedar-van"]
    assert client.get("/api/v1/public/cedar-van/catalog").json()["redirected_from"] == "cedar-van"

    # A slug is not authorization: the other owner cannot manage it, nor read owner settings.
    crossed = client.get(f"/api/v1/tenants/{tenant}/storefront", headers=_auth(other_token))
    assert crossed.status_code == 403
    assert client.get("/api/v1/public/no-such-shop/catalog").status_code == 404
    for reserved in sorted(RESERVED_SLUGS)[:3]:
        assert client.get(f"/api/v1/public/{reserved}/catalog").status_code == 404


def test_suspended_storefront_is_visible_but_not_accepting_and_closed_is_gone(
    client, session_factory
):
    _owner, tenant, token = _owner_context(client, session_factory, "store-status")
    _category, product, _customer = _catalog(client, tenant, token)
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    admin = _user(session_factory, "store.admin@example.com", SystemUserType.ADMIN)
    admin_token = _login(client, admin.email)
    suspended = client.post(
        f"/api/v1/platform/tenants/{tenant}/suspend",
        headers=_auth(admin_token),
        json={"reason": "SUBSCRIPTION_OVERDUE"},
    )
    assert suspended.status_code == 200, suspended.text
    card = client.get(f"/api/v1/public/{slug}/catalog").json()
    assert card["accepting_orders"] is False and card["published_products"] == 1
    with session_factory() as db:
        row = db.get(Tenant, UUID(tenant))
        assert row is not None
        row.status = "CLOSED"
        db.commit()
    assert client.get(f"/api/v1/public/{slug}/catalog").status_code == 404


def test_new_tenants_get_name_derived_unique_slugs(client, session_factory):
    _owner_1, tenant_1, _token_1 = _owner_context(client, session_factory, "twin")
    _owner_2, tenant_2, _token_2 = _owner_context(client, session_factory, "twin-2")
    with session_factory() as db:
        first = db.get(Tenant, UUID(tenant_1))
        second = db.get(Tenant, UUID(tenant_2))
        assert first is not None and second is not None
        assert first.slug == "route-twin" and second.slug == "route-twin-2"
        membership = db.scalar(
            select(TenantMembership).where(TenantMembership.tenant_id == first.id)
        )
        assert membership is not None
        # Direct tenant rows (fixtures) still get a placeholder slug.
        placeholder = Tenant(name="Placeholder")
        db.add(placeholder)
        db.commit()
        assert placeholder.slug.startswith("shop-") and len(placeholder.slug) == 15
        assert uuid4  # imported for parity with sibling modules
