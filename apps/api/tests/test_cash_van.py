from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.cli.import_master_catalog import DEFAULT_DATASET_PATH
from tawzeevo_api.config import get_settings
from tawzeevo_api.errors import AppError
from tawzeevo_api.main import app
from tawzeevo_api.models import (
    BarcodePackageLevel,
    Category,
    Customer,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    MasterBarcode,
    MasterCatalogImport,
    MasterCategory,
    MasterProduct,
    MasterProductImage,
    MasterProductSource,
    ProductGradePrice,
    SystemUserType,
    Tenant,
    TenantBarcode,
    TenantGradeDiscount,
    TenantMembership,
    TenantProduct,
    TenantProductImage,
    User,
)
from tawzeevo_api.routes.cash_van import _storage_dependency
from tawzeevo_api.security import hash_password
from tawzeevo_api.services.catalog_import import import_catalog_dataset, load_catalog_dataset
from tawzeevo_api.services.media import LocalObjectStorage, process_product_image

PASSWORD = "correct horse battery staple"


def create_user(
    session_factory: sessionmaker[Session], email: str, user_type: SystemUserType
) -> User:
    with session_factory() as db:
        user = User(
            first_name="Rana",
            last_name="Khoury",
            email=email,
            phone="+96170123456",
            city="Beirut",
            age=32,
            type=user_type,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def login(client: TestClient, email: str) -> str:
    response = client.post("/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def onboard_owner(
    client: TestClient,
    session_factory: sessionmaker[Session],
    admin_token: str,
    *,
    email: str,
    business_name: str,
) -> tuple[User, str, str]:
    owner = create_user(session_factory, email, SystemUserType.CLIENT)
    owner_token = login(client, owner.email)
    application = client.post(
        "/api/v1/tenant-applications",
        headers=auth(owner_token),
        json={"business_name": business_name},
    )
    assert application.status_code == 201, application.text
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{application.json()['id']}/approve",
        headers=auth(admin_token),
    )
    assert approved.status_code == 200, approved.text
    return owner, str(approved.json()["tenant_id"]), owner_token


def create_category(client: TestClient, tenant_id: str, owner_token: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        headers=auth(owner_token),
        json={
            "name_en": "Beverages",
            "name_ar": "مشروبات",
            "slug": "beverages",
            "display_order": 0,
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def create_product(
    client: TestClient,
    tenant_id: str,
    owner_token: str,
    category_id: object,
    *,
    barcode: str = "5280000000012",
    currency: str = "USD",
    unit_price: str = "12.5000",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=auth(owner_token),
        json={
            "category_id": category_id,
            "name": "Cedar Sparkling Water",
            "barcode": barcode,
            "unit_price": unit_price,
            "currency": currency,
            "price_basis": "PIECE",
            "pieces_per_box": 12,
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def create_customer(
    client: TestClient,
    tenant_id: str,
    owner_token: str,
    *,
    name: str = "Maya Market",
    phone: str = "+961 70 123 456",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/tenants/{tenant_id}/customers",
        headers=auth(owner_token),
        json={"name": name, "phone": phone, "address": "Hamra, Beirut"},
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def test_owner_uses_real_customer_catalog_barcode_and_draft_invoice_slice(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    owner, tenant_id, owner_token = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner@example.com",
        business_name="North Route",
    )

    first_customer = create_customer(client, tenant_id, owner_token)
    second_customer = create_customer(
        client,
        tenant_id,
        owner_token,
        name="Maya Market - Branch 2",
        phone="70123456",
    )
    search = client.get(
        f"/api/v1/tenants/{tenant_id}/customers/search",
        headers=auth(owner_token),
        params={"phone": "+96170123456"},
    )
    assert search.status_code == 200, search.text
    assert [item["id"] for item in search.json()["customers"]] == [
        first_customer["id"],
        second_customer["id"],
    ]

    category = create_category(client, tenant_id, owner_token)
    listed_categories = client.get(
        f"/api/v1/tenants/{tenant_id}/categories", headers=auth(owner_token)
    )
    assert listed_categories.status_code == 200
    assert listed_categories.json()["categories"][0]["id"] == category["id"]
    product = create_product(client, tenant_id, owner_token, category["id"])
    assert product["piece_price"] == "12.5000"
    assert product["box_price"] == "150.0000"
    barcode_result = client.get(
        f"/api/v1/tenants/{tenant_id}/products/barcode/{product['barcode']}",
        headers=auth(owner_token),
    )
    assert barcode_result.status_code == 200
    assert barcode_result.json()["id"] == product["id"]

    created_invoice = client.post(
        f"/api/v1/tenants/{tenant_id}/invoices",
        headers=auth(owner_token),
        json={
            "customer_id": first_customer["id"],
            "items": [{"product_id": product["id"], "quantity": "2.0000"}],
        },
    )
    assert created_invoice.status_code == 201, created_invoice.text
    invoice = created_invoice.json()
    assert invoice["status"] == "DRAFT"
    assert invoice["customer"]["id"] == first_customer["id"]
    assert invoice["items"][0]["product_id"] == product["id"]
    assert invoice["items"][0]["product_name"] == product["name"]
    assert invoice["items"][0]["line_total"] == "25.0000"
    assert invoice["subtotal"] == "25.0000"
    viewed_invoice = client.get(
        f"/api/v1/tenants/{tenant_id}/invoices/{invoice['id']}",
        headers=auth(owner_token),
    )
    assert viewed_invoice.status_code == 200
    assert viewed_invoice.json() == invoice

    with session_factory() as db:
        membership = db.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == UUID(tenant_id),
                TenantMembership.user_id == owner.id,
            )
        )
        assert membership is not None and membership.role.value == "owner"
        assert db.get(Tenant, UUID(tenant_id)).status.value == "ACTIVE"  # type: ignore[union-attr]
        assert db.scalar(select(func.count()).select_from(Customer)) == 2
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(InvoiceRevisionItem)) == 1


def test_unapproved_rejected_admin_and_other_tenant_cannot_access_private_slice(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    admin_token = login(client, admin.email)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="owner-a@example.com",
        business_name="Tenant A",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="owner-b@example.com",
        business_name="Tenant B",
    )
    unapproved = create_user(session_factory, "unapproved@example.com", SystemUserType.CLIENT)
    rejected = create_user(session_factory, "rejected@example.com", SystemUserType.CLIENT)
    rejected_token = login(client, rejected.email)
    rejected_application = client.post(
        "/api/v1/tenant-applications",
        headers=auth(rejected_token),
        json={"business_name": "Rejected Route"},
    )
    assert rejected_application.status_code == 201
    assert (
        client.post(
            f"/api/v1/platform/tenant-applications/{rejected_application.json()['id']}/reject",
            headers=auth(admin_token),
        ).status_code
        == 200
    )

    customer_a = create_customer(client, tenant_a, token_a)
    category_a = create_category(client, tenant_a, token_a)
    product_a = create_product(client, tenant_a, token_a, category_a["id"])

    for denied_token in (token_b, rejected_token, login(client, unapproved.email), admin_token):
        denied = client.get(
            f"/api/v1/tenants/{tenant_a}/customers/{customer_a['id']}",
            headers=auth(denied_token),
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "TENANT_MEMBERSHIP_REQUIRED"

    hidden_from_tenant_b = client.get(
        f"/api/v1/tenants/{tenant_b}/customers/{customer_a['id']}", headers=auth(token_b)
    )
    assert hidden_from_tenant_b.status_code == 404
    category_b = create_category(client, tenant_b, token_b)
    product_b = create_product(
        client, tenant_b, token_b, category_b["id"], barcode=str(product_a["barcode"])
    )
    assert product_b["tenant_id"] == tenant_b

    wrong_category = client.post(
        f"/api/v1/tenants/{tenant_b}/products",
        headers=auth(token_b),
        json={
            "category_id": category_a["id"],
            "name": "Cross-tenant product",
            "barcode": "5280000000098",
            "unit_price": "3.0000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert wrong_category.status_code == 404
    assert wrong_category.json()["detail"]["code"] == "CATEGORY_NOT_FOUND"


def test_suspension_blocks_slice_and_reactivation_preserves_business_rows(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    admin_token = login(client, admin.email)
    _owner, tenant_id, owner_token = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="owner@example.com",
        business_name="Retained Route",
    )
    customer = create_customer(client, tenant_id, owner_token)
    category = create_category(client, tenant_id, owner_token)
    product = create_product(client, tenant_id, owner_token, category["id"])
    invoice = client.post(
        f"/api/v1/tenants/{tenant_id}/invoices",
        headers=auth(owner_token),
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": product["id"], "quantity": "1.0000"}],
        },
    ).json()

    suspended = client.post(
        f"/api/v1/platform/tenants/{tenant_id}/suspend", headers=auth(admin_token)
    )
    assert suspended.status_code == 200
    blocked = client.get(
        f"/api/v1/tenants/{tenant_id}/invoices/{invoice['id']}", headers=auth(owner_token)
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "TENANT_SUSPENDED"
    blocked_write = client.post(
        f"/api/v1/tenants/{tenant_id}/customers",
        headers=auth(owner_token),
        json={"name": "Blocked", "phone": "+96171111222"},
    )
    assert blocked_write.status_code == 403

    reactivated = client.post(
        f"/api/v1/platform/tenants/{tenant_id}/reactivate", headers=auth(admin_token)
    )
    assert reactivated.status_code == 200
    preserved = client.get(
        f"/api/v1/tenants/{tenant_id}/invoices/{invoice['id']}", headers=auth(owner_token)
    )
    assert preserved.status_code == 200
    assert preserved.json()["customer"]["id"] == customer["id"]
    assert preserved.json()["items"][0]["product_id"] == product["id"]


def test_money_packaging_currency_and_barcode_invariants(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    _owner, tenant_id, owner_token = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner@example.com",
        business_name="Pricing Route",
    )
    customer = create_customer(client, tenant_id, owner_token)
    category = create_category(client, tenant_id, owner_token)
    usd_product = create_product(client, tenant_id, owner_token, category["id"])
    lbp_product = create_product(
        client,
        tenant_id,
        owner_token,
        category["id"],
        barcode="5280000000029",
        currency="LBP",
        unit_price="90000.0000",
    )

    duplicate_barcode = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=auth(owner_token),
        json={
            "category_id": category["id"],
            "name": "Duplicate",
            "barcode": usd_product["barcode"],
            "unit_price": "4.0000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert duplicate_barcode.status_code == 409
    missing_piece_count = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=auth(owner_token),
        json={
            "category_id": category["id"],
            "name": "Box product",
            "barcode": "5280000000036",
            "unit_price": "24.0000",
            "currency": "USD",
            "price_basis": "BOX",
        },
    )
    assert missing_piece_count.status_code == 422

    mixed_currency = client.post(
        f"/api/v1/tenants/{tenant_id}/invoices",
        headers=auth(owner_token),
        json={
            "customer_id": customer["id"],
            "items": [
                {"product_id": usd_product["id"], "quantity": "1.0000"},
                {"product_id": lbp_product["id"], "quantity": "1.0000"},
            ],
        },
    )
    assert mixed_currency.status_code == 400
    assert mixed_currency.json()["detail"]["code"] == "CURRENCY_MISMATCH"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0


def test_new_business_tables_have_forced_tenant_rls_and_no_inventory_fields(
    session_factory: sessionmaker[Session],
) -> None:
    table_names = {
        "customers",
        "categories",
        "tenant_products",
        "tenant_barcodes",
        "invoices",
        "invoice_revisions",
        "invoice_revision_items",
        "tenant_grade_discounts",
        "product_grade_prices",
        "tenant_product_images",
    }
    with session_factory() as db:
        rls_rows = db.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname IN ('customers', 'categories', 'tenant_products', "
                "'tenant_barcodes', 'invoices', 'invoice_revisions', "
                "'invoice_revision_items', "
                "'tenant_grade_discounts', 'product_grade_prices', "
                "'tenant_product_images')"
            )
        ).all()
        assert {row.relname for row in rls_rows} == table_names
        assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls_rows)
        policy_tables = set(
            db.scalars(
                text(
                    "SELECT tablename FROM pg_policies WHERE policyname LIKE "
                    "'%_tenant_isolation' AND tablename IN ('customers', 'categories', "
                    "'tenant_products', 'tenant_barcodes', 'invoices', "
                    "'invoice_revisions', 'invoice_revision_items', "
                    "'tenant_grade_discounts', 'product_grade_prices', "
                    "'tenant_product_images')"
                )
            )
        )
        assert policy_tables == table_names
        master_rls = db.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname IN ('master_products', 'master_barcodes', "
                "'master_product_images', 'master_catalog_imports', "
                "'master_product_sources')"
            )
        ).all()
        assert {row.relname for row in master_rls} == {
            "master_products",
            "master_barcodes",
            "master_product_images",
            "master_catalog_imports",
            "master_product_sources",
        }
        assert all(row.relrowsecurity and not row.relforcerowsecurity for row in master_rls)

    forbidden_fragments = ("stock", "availability", "warehouse", "reserved")
    for table in (
        Customer.__table__,
        Category.__table__,
        TenantProduct.__table__,
        TenantBarcode.__table__,
        Invoice.__table__,
        InvoiceRevisionItem.__table__,
        TenantGradeDiscount.__table__,
        ProductGradePrice.__table__,
        TenantProductImage.__table__,
    ):
        assert all(
            fragment not in column.name.lower()
            for column in table.columns
            for fragment in forbidden_fragments
        )
        assert "tenant_id" in table.columns
    for table in (
        MasterProduct.__table__,
        MasterBarcode.__table__,
        MasterProductImage.__table__,
        MasterCatalogImport.__table__,
        MasterProductSource.__table__,
    ):
        assert all(
            fragment not in column.name.lower()
            for column in table.columns
            for fragment in forbidden_fragments
        )
    assert TenantProduct.__table__.c.unit_price.type.scale == 4
    assert InvoiceRevision.__table__.c.subtotal.type.scale == 4
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")


def test_customer_grades_locations_updates_and_duplicate_phone_disambiguation(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner-a@example.com",
        business_name="Tenant A",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner-b@example.com",
        business_name="Tenant B",
    )

    first = client.post(
        f"/api/v1/tenants/{tenant_a}/customers",
        headers=auth(token_a),
        json={
            "name": "Maya Market",
            "phone": "+961 70 123 456",
            "address": "Hamra, Beirut",
            "latitude": "33.895920",
            "longitude": "35.478430",
            "grade": "A+",
        },
    )
    second = client.post(
        f"/api/v1/tenants/{tenant_a}/customers",
        headers=auth(token_a),
        json={
            "name": "Maya Market — Branch 2",
            "phone": "70123456",
            "address": "Verdun, Beirut",
            "grade": "B+",
        },
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["phone"] == second.json()["phone"] == "+96170123456"

    search = client.get(
        f"/api/v1/tenants/{tenant_a}/customers/search",
        headers=auth(token_a),
        params={"phone": "70 123 456"},
    )
    assert search.status_code == 200
    matches = search.json()["customers"]
    assert [match["id"] for match in matches] == [first.json()["id"], second.json()["id"]]
    assert [(match["address"], match["grade"]) for match in matches] == [
        ("Hamra, Beirut", "A+"),
        ("Verdun, Beirut", "B+"),
    ]

    updated = client.put(
        f"/api/v1/tenants/{tenant_a}/customers/{second.json()['id']}",
        headers=auth(token_a),
        json={
            "address": "Achrafieh, Beirut",
            "latitude": "33.889800",
            "longitude": "35.501800",
            "grade": "A",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["grade"] == "A"
    assert updated.json()["latitude"] == "33.889800"
    assert (
        client.put(
            f"/api/v1/tenants/{tenant_b}/customers/{first.json()['id']}",
            headers=auth(token_b),
            json={"grade": "B"},
        ).status_code
        == 404
    )
    invalid_coordinates = client.post(
        f"/api/v1/tenants/{tenant_a}/customers",
        headers=auth(token_a),
        json={"name": "Invalid", "phone": "+96171111111", "latitude": "33.9"},
    )
    assert invalid_coordinates.status_code == 422


def test_bilingual_category_order_master_link_archive_and_slug_invariants(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    _owner, tenant_id, owner_token = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner@example.com",
        business_name="Category Route",
    )
    with session_factory() as db:
        master = MasterCategory(name_en="Beverages", name_ar="مشروبات")
        db.add(master)
        db.commit()
        db.refresh(master)
        master_id = str(master.id)

    later = client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        headers=auth(owner_token),
        json={"name_en": "Snacks", "name_ar": "وجبات خفيفة", "slug": "Snacks", "display_order": 20},
    )
    first = client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        headers=auth(owner_token),
        json={
            "master_category_id": master_id,
            "name_en": "Cold drinks",
            "name_ar": "مشروبات باردة",
            "slug": "Cold Drinks",
            "display_order": 10,
        },
    )
    assert later.status_code == first.status_code == 201
    assert first.json()["slug"] == "cold-drinks"
    assert first.json()["master_category_id"] == master_id

    duplicate = client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        headers=auth(owner_token),
        json={"name_en": "Other", "name_ar": "أخرى", "slug": "cold_drinks"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "CATEGORY_SLUG_ALREADY_EXISTS"

    listed = client.get(f"/api/v1/tenants/{tenant_id}/categories", headers=auth(owner_token))
    assert [item["id"] for item in listed.json()["categories"]] == [
        first.json()["id"],
        later.json()["id"],
    ]
    updated = client.put(
        f"/api/v1/tenants/{tenant_id}/categories/{later.json()['id']}",
        headers=auth(owner_token),
        json={"display_order": 5, "name_ar": "مأكولات خفيفة"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_order"] == 5

    archived = client.post(
        f"/api/v1/tenants/{tenant_id}/categories/{first.json()['id']}/archive",
        headers=auth(owner_token),
    )
    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    active = client.get(
        f"/api/v1/tenants/{tenant_id}/categories", headers=auth(owner_token)
    ).json()["categories"]
    assert [item["id"] for item in active] == [later.json()["id"]]
    retained = client.get(
        f"/api/v1/tenants/{tenant_id}/categories?include_archived=true",
        headers=auth(owner_token),
    ).json()["categories"]
    assert {item["id"] for item in retained} == {first.json()["id"], later.json()["id"]}
    product = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=auth(owner_token),
        json={
            "category_id": first.json()["id"],
            "name": "Hidden category product",
            "barcode": "5280000000999",
            "unit_price": "2.0000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert product.status_code == 404


def test_authenticated_user_lists_only_their_tenant_contexts(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner-a@example.com",
        business_name="Alpha Route",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner-b@example.com",
        business_name="Beta Route",
    )
    contexts_a = client.get("/api/v1/tenant-contexts", headers=auth(token_a))
    assert contexts_a.status_code == 200, contexts_a.text
    assert contexts_a.json()["tenants"] == [
        {
            "membership_id": contexts_a.json()["tenants"][0]["membership_id"],
            "tenant_id": tenant_a,
            "tenant_name": "Alpha Route",
            "tenant_status": "ACTIVE",
            "role": "owner",
        }
    ]
    assert (
        client.get("/api/v1/tenant-contexts", headers=auth(token_b)).json()["tenants"][0][
            "tenant_id"
        ]
        == tenant_b
    )


def test_known_master_barcode_scans_then_adopts_with_tenant_price_and_publication(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as db:
        master = MasterProduct(name="Cedar Sparkling Water")
        db.add(master)
        db.flush()
        db.add_all(
            [
                MasterBarcode(
                    master_product_id=master.id,
                    barcode="5285001111111",
                    package_level=BarcodePackageLevel.PIECE,
                ),
                MasterBarcode(
                    master_product_id=master.id,
                    barcode="5285001111128",
                    package_level=BarcodePackageLevel.BOX,
                ),
            ]
        )
        db.commit()
        master_id = str(master.id)

    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    _owner, tenant_id, owner_token = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner@example.com",
        business_name="Master Catalog Route",
    )
    category = create_category(client, tenant_id, owner_token)

    scan = client.get(
        f"/api/v1/tenants/{tenant_id}/catalog/barcodes/5285001111111",
        headers=auth(owner_token),
    )
    assert scan.status_code == 200, scan.text
    assert scan.json()["ownership"] == "MASTER"
    assert scan.json()["package_level"] == "PIECE"
    assert scan.json()["master_product"]["id"] == master_id
    assert scan.json()["tenant_product"] is None

    adopted = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=auth(owner_token),
        json={
            "category_id": category["id"],
            "master_product_id": master_id,
            "name": "Cedar Water — Tenant Label",
            "barcode": "5285001111111",
            "unit_price": "3.2500",
            "currency": "USD",
            "price_basis": "PIECE",
            "pieces_per_box": 12,
            "is_published": True,
        },
    )
    assert adopted.status_code == 201, adopted.text
    product = adopted.json()
    assert product["master_product_id"] == master_id
    assert product["is_published"] is True
    assert product["piece_price"] == "3.2500"
    assert {
        (item["barcode"], item["ownership"], item["package_level"]) for item in product["barcodes"]
    } == {
        ("5285001111111", "MASTER", "PIECE"),
        ("5285001111128", "MASTER", "BOX"),
    }

    box_scan = client.get(
        f"/api/v1/tenants/{tenant_id}/catalog/barcodes/5285001111128",
        headers=auth(owner_token),
    )
    assert box_scan.status_code == 200
    assert box_scan.json()["package_level"] == "BOX"
    assert box_scan.json()["tenant_product"]["id"] == product["id"]
    assert box_scan.json()["tenant_product"]["barcode"] == "5285001111128"
    assert box_scan.json()["tenant_product"]["unit_price"] == "3.2500"

    duplicate = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=auth(owner_token),
        json={
            "category_id": category["id"],
            "master_product_id": master_id,
            "name": "Duplicate adoption",
            "barcode": "5285001111111",
            "unit_price": "4.0000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "MASTER_PRODUCT_ALREADY_ADOPTED"
    listed = client.get(f"/api/v1/tenants/{tenant_id}/products", headers=auth(owner_token))
    assert [item["id"] for item in listed.json()["products"]] == [product["id"]]


def test_unknown_barcode_manual_product_extra_package_barcode_and_visibility_update(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner-a@example.com",
        business_name="Manual Product Route",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        login(client, admin.email),
        email="owner-b@example.com",
        business_name="Other Route",
    )
    category_a = create_category(client, tenant_a, token_a)
    category_b = create_category(client, tenant_b, token_b)

    unknown = client.get(
        f"/api/v1/tenants/{tenant_a}/catalog/barcodes/TENANT-BOX-001",
        headers=auth(token_a),
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "BARCODE_NOT_FOUND"

    created = client.post(
        f"/api/v1/tenants/{tenant_a}/products",
        headers=auth(token_a),
        json={
            "category_id": category_a["id"],
            "name": "Manual olive oil",
            "barcode": "TENANT-BOX-001",
            "barcode_package_level": "BOX",
            "unit_price": "9.5000",
            "currency": "USD",
            "price_basis": "PIECE",
            "pieces_per_box": 6,
        },
    )
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["master_product_id"] is None
    assert product["is_published"] is False
    assert product["barcodes"][0]["ownership"] == "TENANT"
    assert product["barcodes"][0]["package_level"] == "BOX"

    extra = client.post(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}/barcodes",
        headers=auth(token_a),
        json={"barcode": "TENANT-PIECE-001", "package_level": "PIECE"},
    )
    assert extra.status_code == 201, extra.text
    assert {item["barcode"] for item in extra.json()["barcodes"]} == {
        "TENANT-BOX-001",
        "TENANT-PIECE-001",
    }
    piece_scan = client.get(
        f"/api/v1/tenants/{tenant_a}/catalog/barcodes/TENANT-PIECE-001",
        headers=auth(token_a),
    )
    assert piece_scan.status_code == 200
    assert piece_scan.json()["ownership"] == "TENANT"
    assert piece_scan.json()["tenant_product"]["id"] == product["id"]

    published = client.put(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}",
        headers=auth(token_a),
        json={"is_published": True},
    )
    assert published.status_code == 200
    assert published.json()["is_published"] is True
    assert "stock" not in published.json()
    assert "availability" not in published.json()

    hidden_cross_tenant = client.get(
        f"/api/v1/tenants/{tenant_b}/catalog/barcodes/TENANT-PIECE-001",
        headers=auth(token_b),
    )
    assert hidden_cross_tenant.status_code == 404
    cross_tenant_mutation = client.post(
        f"/api/v1/tenants/{tenant_b}/products/{product['id']}/barcodes",
        headers=auth(token_b),
        json={"barcode": "OTHER", "package_level": "PIECE"},
    )
    assert cross_tenant_mutation.status_code == 404
    same_barcode_other_tenant = client.post(
        f"/api/v1/tenants/{tenant_b}/products",
        headers=auth(token_b),
        json={
            "category_id": category_b["id"],
            "name": "Other tenant product",
            "barcode": "TENANT-PIECE-001",
            "unit_price": "7.0000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert same_barcode_other_tenant.status_code == 201

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TenantBarcode)) == 3


def test_pricing_v1_precedence_rounding_packaging_and_invoice_snapshot(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    admin_token = login(client, admin.email)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="pricing-owner@example.com",
        business_name="Pricing Route",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="other-pricing-owner@example.com",
        business_name="Other Pricing Route",
    )
    category_a = create_category(client, tenant_a, token_a)
    category_b = create_category(client, tenant_b, token_b)
    customer = client.post(
        f"/api/v1/tenants/{tenant_a}/customers",
        headers=auth(token_a),
        json={"name": "Grade A Market", "phone": "+96170123123", "grade": "A"},
    )
    assert customer.status_code == 201, customer.text
    product = create_product(
        client,
        tenant_a,
        token_a,
        category_a["id"],
        barcode="PRICING-PIECE-001",
        unit_price="10.0050",
    )

    discount = client.put(
        f"/api/v1/tenants/{tenant_a}/grade-discounts/A",
        headers=auth(token_a),
        json={"discount_percent": "12.3456"},
    )
    assert discount.status_code == 200, discount.text
    assert discount.json()["discount_percent"] == "12.3456"
    discounted = client.get(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}/pricing",
        headers=auth(token_a),
        params={"customer_id": customer.json()["id"]},
    )
    assert discounted.status_code == 200, discounted.text
    assert discounted.json() == {
        "product_id": product["id"],
        "customer_id": customer.json()["id"],
        "customer_grade": "A",
        "source": "GRADE_DISCOUNT",
        "discount_percent": "12.3456",
        "currency": "USD",
        "price_basis": "PIECE",
        "basis_price": "8.7698",
        "piece_price": "8.7698",
        "box_price": "105.2376",
    }

    explicit = client.put(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}/grade-prices/A",
        headers=auth(token_a),
        json={"unit_price": "9.8765"},
    )
    assert explicit.status_code == 200, explicit.text
    explicit_resolution = client.get(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}/pricing",
        headers=auth(token_a),
        params={"customer_id": customer.json()["id"]},
    ).json()
    assert explicit_resolution["source"] == "EXPLICIT_GRADE_PRICE"
    assert explicit_resolution["discount_percent"] is None
    assert explicit_resolution["basis_price"] == "9.8765"
    assert explicit_resolution["box_price"] == "118.5180"

    blocked_basis_change = client.put(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}",
        headers=auth(token_a),
        json={"price_basis": "BOX"},
    )
    assert blocked_basis_change.status_code == 409
    assert blocked_basis_change.json()["detail"]["code"] == "GRADE_PRICES_REQUIRE_RESET"

    invoice_response = client.post(
        f"/api/v1/tenants/{tenant_a}/invoices",
        headers=auth(token_a),
        json={
            "customer_id": customer.json()["id"],
            "items": [{"product_id": product["id"], "quantity": "2.0000"}],
        },
    )
    assert invoice_response.status_code == 201, invoice_response.text
    invoice = invoice_response.json()
    assert invoice["subtotal"] == "19.7530"
    assert invoice["items"][0]["unit_price"] == "9.8765"
    assert invoice["items"][0]["customer_grade"] == "A"
    assert invoice["items"][0]["price_source"] == "EXPLICIT_GRADE_PRICE"
    assert invoice["items"][0]["grade_discount_percent"] is None

    changed_explicit = client.put(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}/grade-prices/A",
        headers=auth(token_a),
        json={"unit_price": "8.0000"},
    )
    assert changed_explicit.status_code == 200
    preserved = client.get(
        f"/api/v1/tenants/{tenant_a}/invoices/{invoice['id']}", headers=auth(token_a)
    )
    assert preserved.status_code == 200
    assert preserved.json()["items"][0]["unit_price"] == "9.8765"
    assert preserved.json()["subtotal"] == "19.7530"

    assert (
        client.delete(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/grade-prices/A",
            headers=auth(token_a),
        ).status_code
        == 204
    )
    tie_discount = client.put(
        f"/api/v1/tenants/{tenant_a}/grade-discounts/A",
        headers=auth(token_a),
        json={"discount_percent": "0.0150"},
    )
    assert tie_discount.status_code == 200, tie_discount.text
    repriced_product = client.put(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}",
        headers=auth(token_a),
        json={"unit_price": "1.0000"},
    )
    assert repriced_product.status_code == 200, repriced_product.text
    tie_resolution = client.get(
        f"/api/v1/tenants/{tenant_a}/products/{product['id']}/pricing",
        headers=auth(token_a),
        params={"customer_id": customer.json()["id"]},
    )
    assert tie_resolution.status_code == 200, tie_resolution.text
    assert tie_resolution.json()["source"] == "GRADE_DISCOUNT"
    assert tie_resolution.json()["discount_percent"] == "0.0150"
    # 1.0000 * (1 - 0.0150 / 100) = 0.99985. HALF_UP must produce
    # 0.9999; HALF_EVEN would incorrectly produce 0.9998.
    assert tie_resolution.json()["basis_price"] == "0.9999"
    assert tie_resolution.json()["piece_price"] == "0.9999"
    assert tie_resolution.json()["box_price"] == "11.9988"

    discounted_invoice_response = client.post(
        f"/api/v1/tenants/{tenant_a}/invoices",
        headers=auth(token_a),
        json={
            "customer_id": customer.json()["id"],
            "items": [{"product_id": product["id"], "quantity": "2.0000"}],
        },
    )
    assert discounted_invoice_response.status_code == 201, discounted_invoice_response.text
    discounted_invoice = discounted_invoice_response.json()
    assert discounted_invoice["subtotal"] == "1.9998"
    assert discounted_invoice["items"][0]["unit_price"] == "0.9999"
    assert discounted_invoice["items"][0]["price_source"] == "GRADE_DISCOUNT"
    assert discounted_invoice["items"][0]["grade_discount_percent"] == "0.0150"

    assert (
        client.delete(
            f"/api/v1/tenants/{tenant_a}/grade-discounts/A", headers=auth(token_a)
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/pricing",
            headers=auth(token_a),
            params={"customer_id": customer.json()["id"]},
        ).json()["source"]
        == "NORMAL"
    )
    preserved_discounted_invoice = client.get(
        f"/api/v1/tenants/{tenant_a}/invoices/{discounted_invoice['id']}",
        headers=auth(token_a),
    )
    assert preserved_discounted_invoice.status_code == 200
    assert preserved_discounted_invoice.json()["items"][0]["unit_price"] == "0.9999"
    assert preserved_discounted_invoice.json()["items"][0]["grade_discount_percent"] == "0.0150"

    box_product = client.post(
        f"/api/v1/tenants/{tenant_a}/products",
        headers=auth(token_a),
        json={
            "category_id": category_a["id"],
            "name": "Thirty-two-piece box",
            "barcode": "PRICING-BOX-001",
            "unit_price": "1.0000",
            "currency": "USD",
            "price_basis": "BOX",
            "pieces_per_box": 32,
        },
    )
    assert box_product.status_code == 201, box_product.text
    # 1.0000 / 32 = 0.03125. The independently quantized counterpart must
    # use HALF_UP and therefore resolve to 0.0313, not HALF_EVEN's 0.0312.
    assert box_product.json()["piece_price"] == "0.0313"
    assert box_product.json()["box_price"] == "1.0000"

    cross_membership = client.get(
        f"/api/v1/tenants/{tenant_a}/grade-discounts", headers=auth(token_b)
    )
    assert cross_membership.status_code == 403
    hidden_product = client.get(
        f"/api/v1/tenants/{tenant_b}/products/{product['id']}", headers=auth(token_b)
    )
    assert hidden_product.status_code == 404
    assert category_b["tenant_id"] == tenant_b


def test_product_image_upload_reencodes_and_scan_returns_tenant_image(
    client: TestClient,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    admin_token = login(client, admin.email)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="media-owner@example.com",
        business_name="Media Route",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="other-media-owner@example.com",
        business_name="Other Media Route",
    )
    category = create_category(client, tenant_a, token_a)
    product = create_product(
        client,
        tenant_a,
        token_a,
        category["id"],
        barcode="MEDIA-001",
    )
    storage_root = tmp_path / "objects"
    app.dependency_overrides[_storage_dependency] = lambda: LocalObjectStorage(storage_root)
    try:
        source = BytesIO()
        Image.new("RGBA", (16, 10), (18, 104, 92, 180)).save(source, format="PNG")
        uploaded = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/images",
            headers=auth(token_a),
            files={"file": ("product.png", source.getvalue(), "image/png")},
            data={"alt_text": "Green bottle", "display_order": "2"},
        )
        assert uploaded.status_code == 201, uploaded.text
        image = uploaded.json()
        assert image["ownership"] == "TENANT"
        assert image["content_type"] == "image/webp"
        # A retried upload of the same bytes (lost response) returns the same asset, no duplicate.
        retried = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/images",
            headers=auth(token_a),
            files={"file": ("product.png", source.getvalue(), "image/png")},
            data={"alt_text": "Green bottle", "display_order": "2"},
        )
        assert retried.status_code == 201, retried.text
        assert retried.json()["id"] == image["id"]
        assert (image["width"], image["height"]) == (16, 10)
        assert image["alt_text"] == "Green bottle"

        content = client.get(image["url"], headers=auth(token_a))
        assert content.status_code == 200
        assert content.headers["content-type"] == "image/webp"
        assert content.headers["x-content-type-options"] == "nosniff"
        with Image.open(BytesIO(content.content)) as decoded:
            assert decoded.format == "WEBP"
            assert decoded.size == (16, 10)

        scan = client.get(
            f"/api/v1/tenants/{tenant_a}/catalog/barcodes/MEDIA-001",
            headers=auth(token_a),
        )
        assert scan.status_code == 200, scan.text
        assert scan.json()["tenant_product"]["images"] == [image]

        svg = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/images",
            headers=auth(token_a),
            files={"file": ("unsafe.svg", b"<svg></svg>", "image/svg+xml")},
        )
        assert svg.status_code == 415
        assert svg.json()["detail"]["code"] == "UNSUPPORTED_IMAGE_TYPE"
        invalid = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/images",
            headers=auth(token_a),
            files={"file": ("spoofed.jpg", b"not an image", "image/jpeg")},
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"]["code"] == "INVALID_IMAGE"
        over_byte_limit = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/images",
            headers=auth(token_a),
            files={
                "file": (
                    "too-large.png",
                    b"x" * (get_settings().media_max_upload_bytes + 1),
                    "image/png",
                )
            },
        )
        assert over_byte_limit.status_code == 413
        assert over_byte_limit.json()["detail"]["code"] == "IMAGE_TOO_LARGE"
        oversized_source = BytesIO()
        Image.new("RGB", (6001, 1), "white").save(oversized_source, format="PNG")
        oversized = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product['id']}/images",
            headers=auth(token_a),
            files={
                "file": (
                    "too-wide.png",
                    oversized_source.getvalue(),
                    "image/png",
                )
            },
        )
        assert oversized.status_code == 413
        assert oversized.json()["detail"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"

        wrong_membership = client.get(image["url"], headers=auth(token_b))
        assert wrong_membership.status_code == 403
        hidden = client.get(
            f"/api/v1/tenants/{tenant_b}/product-images/TENANT/{image['id']}/content",
            headers=auth(token_b),
        )
        assert hidden.status_code == 404
        assert len(list(storage_root.rglob("*.webp"))) == 1
    finally:
        app.dependency_overrides.pop(_storage_dependency, None)


def test_media_processor_accepts_supported_formats_and_storage_blocks_traversal(
    tmp_path: Path,
) -> None:
    for source_format, declared_type in (
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
        ("WEBP", "image/webp"),
    ):
        source = BytesIO()
        Image.new("RGB", (8, 6), "navy").save(source, format=source_format)
        processed = process_product_image(source.getvalue(), declared_type)
        assert processed.content_type == "image/webp"
        assert (processed.width, processed.height) == (8, 6)
        with Image.open(BytesIO(processed.content)) as decoded:
            assert decoded.format == "WEBP"
            assert decoded.size == (8, 6)

    storage = LocalObjectStorage(tmp_path / "safe-objects")
    try:
        storage.put_bytes("../outside.webp", b"unsafe")
    except AppError as exc:
        assert exc.status_code == 400
        assert exc.code == "INVALID_MEDIA_KEY"
    else:
        raise AssertionError("Local media storage accepted a traversal object key")
    assert not (tmp_path / "outside.webp").exists()


def test_imported_catalog_scan_returns_tenant_image_price_and_isolated_grade_pricing(
    client: TestClient,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    with session_factory() as db:
        imported = import_catalog_dataset(db, load_catalog_dataset(DEFAULT_DATASET_PATH))
        assert imported.inserted_count == 4

    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    admin_token = login(client, admin.email)
    _owner_a, tenant_a, token_a = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="catalog-owner-a@example.com",
        business_name="Catalog Route A",
    )
    _owner_b, tenant_b, token_b = onboard_owner(
        client,
        session_factory,
        admin_token,
        email="catalog-owner-b@example.com",
        business_name="Catalog Route B",
    )
    category_a = create_category(client, tenant_a, token_a)
    category_b = create_category(client, tenant_b, token_b)
    barcode = "5283003202007"

    master_scan = client.get(
        f"/api/v1/tenants/{tenant_a}/catalog/barcodes/{barcode}",
        headers=auth(token_a),
    )
    assert master_scan.status_code == 200, master_scan.text
    master_product = master_scan.json()["master_product"]
    assert master_product["name"] == "Hummus tahini"
    assert master_scan.json()["tenant_product"] is None

    def adopt_product(
        tenant_id: str, token: str, category_id: str, price: str
    ) -> dict[str, object]:
        response = client.post(
            f"/api/v1/tenants/{tenant_id}/products",
            headers=auth(token),
            json={
                "category_id": category_id,
                "master_product_id": master_product["id"],
                "name": master_product["name"],
                "barcode": barcode,
                "barcode_package_level": "PIECE",
                "unit_price": price,
                "currency": "USD",
                "price_basis": "PIECE",
                "pieces_per_box": 6,
                "is_published": True,
            },
        )
        assert response.status_code == 201, response.text
        result: dict[str, object] = response.json()
        return result

    product_a = adopt_product(tenant_a, token_a, str(category_a["id"]), "3.2500")
    customer_a = client.post(
        f"/api/v1/tenants/{tenant_a}/customers",
        headers=auth(token_a),
        json={"name": "Grade A Shop", "phone": "+96170111001", "grade": "A"},
    )
    assert customer_a.status_code == 201, customer_a.text
    assert (
        client.put(
            f"/api/v1/tenants/{tenant_a}/grade-discounts/A",
            headers=auth(token_a),
            json={"discount_percent": "10.0000"},
        ).status_code
        == 200
    )

    storage_root = tmp_path / "catalog-objects"
    app.dependency_overrides[_storage_dependency] = lambda: LocalObjectStorage(storage_root)
    try:
        source = BytesIO()
        Image.new("RGB", (12, 12), "orange").save(source, format="PNG")
        uploaded = client.post(
            f"/api/v1/tenants/{tenant_a}/products/{product_a['id']}/images",
            headers=auth(token_a),
            files={"file": ("hummus.png", source.getvalue(), "image/png")},
            data={"alt_text": "Hummus product"},
        )
        assert uploaded.status_code == 201, uploaded.text

        scan_a = client.get(
            f"/api/v1/tenants/{tenant_a}/catalog/barcodes/{barcode}",
            headers=auth(token_a),
        )
        assert scan_a.status_code == 200, scan_a.text
        assert scan_a.json()["master_product"]["name"] == "Hummus tahini"
        assert scan_a.json()["tenant_product"]["unit_price"] == "3.2500"
        assert scan_a.json()["tenant_product"]["images"] == [uploaded.json()]

        pricing_a = client.get(
            f"/api/v1/tenants/{tenant_a}/products/{product_a['id']}/pricing",
            headers=auth(token_a),
            params={"customer_id": customer_a.json()["id"]},
        )
        assert pricing_a.status_code == 200, pricing_a.text
        assert pricing_a.json()["source"] == "GRADE_DISCOUNT"
        assert pricing_a.json()["basis_price"] == "2.9250"

        isolated_scan_b = client.get(
            f"/api/v1/tenants/{tenant_b}/catalog/barcodes/{barcode}",
            headers=auth(token_b),
        )
        assert isolated_scan_b.status_code == 200, isolated_scan_b.text
        assert isolated_scan_b.json()["master_product"]["name"] == "Hummus tahini"
        assert isolated_scan_b.json()["tenant_product"] is None

        product_b = adopt_product(tenant_b, token_b, str(category_b["id"]), "4.5000")
        scan_b = client.get(
            f"/api/v1/tenants/{tenant_b}/catalog/barcodes/{barcode}",
            headers=auth(token_b),
        )
        assert scan_b.status_code == 200, scan_b.text
        assert scan_b.json()["tenant_product"]["id"] == product_b["id"]
        assert scan_b.json()["tenant_product"]["unit_price"] == "4.5000"
        assert scan_b.json()["tenant_product"]["images"] == []

        cross_tenant_product = client.get(
            f"/api/v1/tenants/{tenant_a}/products/{product_a['id']}",
            headers=auth(token_b),
        )
        assert cross_tenant_product.status_code == 403
        unchanged_a = client.get(
            f"/api/v1/tenants/{tenant_a}/products/{product_a['id']}/pricing",
            headers=auth(token_a),
            params={"customer_id": customer_a.json()["id"]},
        )
        assert unchanged_a.json()["basis_price"] == "2.9250"
    finally:
        app.dependency_overrides.pop(_storage_dependency, None)
