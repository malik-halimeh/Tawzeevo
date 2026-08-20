from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.models import (
    Category,
    Customer,
    Invoice,
    InvoiceItem,
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantProduct,
    User,
)
from tawzeevo_api.security import hash_password

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
        json={"name": "Beverages"},
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
        assert db.scalar(select(func.count()).select_from(InvoiceItem)) == 1


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
    table_names = {"customers", "categories", "tenant_products", "invoices", "invoice_items"}
    with session_factory() as db:
        rls_rows = db.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname IN ('customers', 'categories', 'tenant_products', "
                "'invoices', 'invoice_items')"
            )
        ).all()
        assert {row.relname for row in rls_rows} == table_names
        assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls_rows)
        policy_tables = set(
            db.scalars(
                text(
                    "SELECT tablename FROM pg_policies WHERE policyname LIKE "
                    "'%_tenant_isolation' AND tablename IN ('customers', 'categories', "
                    "'tenant_products', 'invoices', 'invoice_items')"
                )
            )
        )
        assert policy_tables == table_names

    forbidden_fragments = ("stock", "availability", "warehouse", "reserved")
    for table in (
        Customer.__table__,
        Category.__table__,
        TenantProduct.__table__,
        Invoice.__table__,
        InvoiceItem.__table__,
    ):
        assert all(
            fragment not in column.name.lower()
            for column in table.columns
            for fragment in forbidden_fragments
        )
        assert "tenant_id" in table.columns
    assert TenantProduct.__table__.c.unit_price.type.scale == 4
    assert Invoice.__table__.c.subtotal.type.scale == 4
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
