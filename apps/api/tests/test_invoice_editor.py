from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AllocationKind,
    AuditEvent,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceSequence,
    LedgerEntryType,
    Payment,
    PaymentAllocation,
    PaymentDirection,
    ProductPriceBasis,
    SystemUserType,
    TenantMembership,
    TenantProduct,
    TenantProductCostEntry,
    TenantRole,
    TenantSupplier,
    User,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.payments import CustomerRefundRequest
from tawzeevo_api.security import hash_password
from tawzeevo_api.services.invoice_finance import confirm_invoice
from tawzeevo_api.services.payments import record_customer_refund

PASSWORD = "correct horse battery staple"


def _user(session_factory: sessionmaker[Session], email: str, user_type: SystemUserType) -> User:
    with session_factory() as db:
        user = User(
            first_name="Rana",
            last_name="Khoury",
            email=email,
            phone=f"+96170{uuid4().int % 1000000:06d}",
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


def _login(client: TestClient, email: str) -> str:
    response = client.post("/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _owner_context(
    client: TestClient, session_factory: sessionmaker[Session], suffix: str
) -> tuple[User, str, str]:
    admin = _user(session_factory, f"admin-{suffix}@example.com", SystemUserType.ADMIN)
    owner = _user(session_factory, f"owner-{suffix}@example.com", SystemUserType.CLIENT)
    owner_token = _login(client, owner.email)
    application = client.post(
        "/api/v1/tenant-applications",
        headers=_auth(owner_token),
        json={"business_name": f"Route {suffix}"},
    )
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{application.json()['id']}/approve",
        headers=_auth(_login(client, admin.email)),
    )
    assert approved.status_code == 200, approved.text
    return owner, str(approved.json()["tenant_id"]), owner_token


def _catalog(
    client: TestClient,
    tenant_id: str,
    token: str,
    *,
    name: str = "Cedar Sparkling Water",
    barcode: str = "5280000000012",
    currency: str = "USD",
    price: str = "12.5000",
    pieces_per_box: int = 12,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    category_response = client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        headers=_auth(token),
        json={
            "name_en": "Beverages",
            "name_ar": "مشروبات",
            "slug": f"beverages-{barcode.lower()}",
        },
    )
    assert category_response.status_code == 201, category_response.text
    product_response = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=_auth(token),
        json={
            "category_id": category_response.json()["id"],
            "name": name,
            "barcode": barcode,
            "unit_price": price,
            "currency": currency,
            "price_basis": "PIECE",
            "pieces_per_box": pieces_per_box,
        },
    )
    assert product_response.status_code == 201, product_response.text
    customer_response = client.post(
        f"/api/v1/tenants/{tenant_id}/customers",
        headers=_auth(token),
        json={"name": "Maya Market", "phone": "+961 70 123 456", "grade": "A"},
    )
    assert customer_response.status_code == 201, customer_response.text
    return category_response.json(), product_response.json(), customer_response.json()


def _draft_payload(
    customer_id: object,
    product_id: object,
    *,
    command_id: str | None = None,
    predecessor_id: str | None = None,
    accepted_match: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "client_command_id": command_id or str(uuid4()),
        "expected_predecessor_revision_id": predecessor_id,
        "customer_id": customer_id,
        "currency": "USD",
        "invoice_discount_expression": "1",
        "invoice_markup_expression": "0.5",
        "items": [
            {
                "product_id": product_id,
                "barcode": "5280000000012",
                "quantity_expression": "1 + 1",
                "price_basis": "PIECE",
                "line_discount_expression": "0.5",
                "line_markup_expression": "0.25",
                "accepted_fuzzy_match": accepted_match,
            },
            {
                "manual_name": "Delivery tray",
                "quantity_expression": "3",
                "price_basis": "PIECE",
                "manual_unit_price": "2.0000",
            },
        ],
    }


def _attach_latest_cost(
    session_factory: sessionmaker[Session],
    owner: User,
    tenant_id: str,
    product_id: object,
) -> None:
    with session_factory() as db:
        product = db.get(TenantProduct, product_id)
        assert product is not None
        supplier = TenantSupplier(tenant_id=tenant_id, name="Confirmation Supplier")
        db.add(supplier)
        db.flush()
        product.preferred_supplier_id = supplier.id
        db.add(
            TenantProductCostEntry(
                tenant_id=tenant_id,
                tenant_product_id=product.id,
                supplier_id=supplier.id,
                unit_cost=Decimal("8.0000"),
                currency="USD",
                cost_basis=ProductPriceBasis.PIECE,
                pieces_per_box=12,
                effective_at=datetime.now(UTC),
                source_type="MANUAL",
                created_by_user_id=owner.id,
            )
        )
        db.commit()


def _confirmable_payload(
    customer_id: object,
    product_id: object,
    *,
    command_id: str | None = None,
    predecessor_id: str | None = None,
) -> dict[str, object]:
    payload = _draft_payload(
        customer_id,
        product_id,
        command_id=command_id,
        predecessor_id=predecessor_id,
    )
    payload["items"] = [payload["items"][0]]  # type: ignore[index]
    return payload


def test_editor_recalculates_pricing_v1_calculator_adjustments_and_immutable_updates(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "pricing")
    _category, product, customer = _catalog(client, tenant_id, token)
    discount = client.put(
        f"/api/v1/tenants/{tenant_id}/grade-discounts/A",
        headers=_auth(token),
        json={"discount_percent": "10.0000"},
    )
    assert discount.status_code == 200, discount.text
    with session_factory() as db:
        db.add(
            CustomerLedgerEntry(
                tenant_id=tenant_id,
                customer_id=customer["id"],
                currency="USD",
                signed_amount=Decimal("5.0000"),
                entry_type=LedgerEntryType.OPENING_BALANCE,
                source_type="TEST_OPENING_BALANCE",
                source_effect_key="opening-balance-pricing",
                effective_at=datetime.now(UTC),
                actor_user_id=_owner.id,
            )
        )
        db.commit()

    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_draft_payload(customer["id"], product["id"]),
    )
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["pricing_version"] == "pricing-v1"
    assert invoice["items"][0]["normal_unit_price"] == "12.5000"
    assert invoice["items"][0]["effective_unit_price"] == "11.2500"
    assert invoice["items"][0]["price_source"] == "GRADE_DISCOUNT"
    assert invoice["items"][0]["line_total"] == "22.2500"
    assert invoice["subtotal"] == "28.5000"
    assert invoice["discount_total"] == "1.5000"
    assert invoice["markup_total"] == "0.7500"
    assert invoice["net_sales"] == "27.7500"
    assert invoice["prior_balance"] == "5.0000"
    assert invoice["total_due"] == "32.7500"
    assert invoice["items"][0]["media_snapshot"] == {"images": []}

    updated_payload = _draft_payload(
        customer["id"],
        product["id"],
        predecessor_id=invoice["current_revision_id"],
    )
    updated_payload["invoice_discount_expression"] = "2 / 2"
    updated = client.put(
        f"/api/v1/invoices/{invoice['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=updated_payload,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["server_revision_number"] == 2
    with session_factory() as db:
        revisions = list(
            db.scalars(
                select(InvoiceRevision)
                .where(InvoiceRevision.invoice_id == invoice["id"])
                .order_by(InvoiceRevision.server_revision_number)
            )
        )
        assert len(revisions) == 2
        assert revisions[0].net_sales == Decimal("27.7500")
        assert revisions[1].predecessor_revision_id == revisions[0].id

    stale = client.put(
        f"/api/v1/invoices/{invoice['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_draft_payload(
            customer["id"], product["id"], predecessor_id=invoice["current_revision_id"]
        ),
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_INVOICE_REVISION"


def test_text_parser_is_exact_first_and_never_auto_selects_fuzzy_or_ambiguous_matches(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "parser")
    category, product, _customer = _catalog(
        client,
        tenant_id,
        token,
        name="مياه الأرز",
        barcode="5280000000012",
    )
    duplicate = client.post(
        f"/api/v1/tenants/{tenant_id}/products",
        headers=_auth(token),
        json={
            "category_id": category["id"],
            "name": "مياه الأرز",
            "barcode": "5280000000098",
            "unit_price": "9.0000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert duplicate.status_code == 201, duplicate.text
    box_barcode = client.post(
        f"/api/v1/tenants/{tenant_id}/products/{product['id']}/barcodes",
        headers=_auth(token),
        json={"barcode": "5280000000013", "package_level": "BOX"},
    )
    assert box_barcode.status_code == 201, box_barcode.text

    ambiguous = client.post(
        "/api/v1/invoices/item-parser",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"text": "٢ مياه الارز"},
    )
    assert ambiguous.status_code == 200, ambiguous.text
    item = ambiguous.json()["items"][0]
    assert item["quantity"] == "2.0000"
    assert item["resolution"] == "AMBIGUOUS"
    assert item["selected"] is None
    assert {match["product_id"] for match in item["suggestions"]} == {
        product["id"],
        duplicate.json()["id"],
    }

    fuzzy = client.post(
        "/api/v1/invoices/item-parser",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"text": "ميه الارز"},
    )
    assert fuzzy.status_code == 200, fuzzy.text
    fuzzy_item = fuzzy.json()["items"][0]
    assert fuzzy_item["selected"] is None
    assert fuzzy_item["resolution"] == "AMBIGUOUS"
    assert all(match["match_type"] == "FUZZY" for match in fuzzy_item["suggestions"])

    exact_barcode = client.post(
        "/api/v1/invoices/item-parser",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"text": "3 x 5280000000012"},
    )
    assert exact_barcode.status_code == 200
    assert exact_barcode.json()["items"][0]["resolution"] == "EXACT"
    assert exact_barcode.json()["items"][0]["selected"]["product_id"] == product["id"]
    exact_box = client.post(
        "/api/v1/invoices/item-parser",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"text": "1 x 5280000000013"},
    )
    assert exact_box.status_code == 200
    assert exact_box.json()["items"][0]["selected"]["barcode"] == "5280000000013"
    assert exact_box.json()["items"][0]["selected"]["package_level"] == "BOX"

    prefix = client.get(
        "/api/v1/invoices/catalog-search",
        params={"tenant_id": tenant_id, "query": "مياه"},
        headers=_auth(token),
    )
    assert prefix.status_code == 200
    assert all(match["match_type"] == "PREFIX" for match in prefix.json()["matches"])


def test_accepted_fuzzy_match_is_audited_and_owner_finance_is_tenant_protected(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "security")
    _category, product, customer = _catalog(client, tenant_id, token)
    accepted = {
        "query": "Cedar Sparklin Water",
        "selected_product_id": product["id"],
        "score": "0.9500",
    }
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_draft_payload(customer["id"], product["id"], accepted_match=accepted),
    )
    assert created.status_code == 201, created.text
    with session_factory() as db:
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "invoice_item_fuzzy_match_accepted",
                AuditEvent.entity_id == created.json()["id"],
            )
        )
        assert audit is not None
        assert audit.actor_user_id == owner.id
        assert audit.details["selected_product_id"] == product["id"]

        driver = User(
            first_name="Dina",
            last_name="Driver",
            email="driver-security@example.com",
            phone="+96170111999",
            city="Beirut",
            age=28,
            type=SystemUserType.CLIENT,
            password_hash=hash_password(PASSWORD),
        )
        db.add(driver)
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=tenant_id,
                user_id=driver.id,
                role=TenantRole.DRIVER,
                is_active=True,
            )
        )
        db.commit()
        driver_email = driver.email
    driver_response = client.get(
        f"/api/v1/invoices/{created.json()['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(_login(client, driver_email)),
    )
    assert driver_response.status_code == 403
    assert driver_response.json()["detail"]["code"] == "TENANT_OWNER_REQUIRED"

    _other_owner, other_tenant_id, other_token = _owner_context(client, session_factory, "other")
    cross_tenant = client.get(
        f"/api/v1/invoices/{created.json()['id']}",
        params={"tenant_id": other_tenant_id},
        headers=_auth(other_token),
    )
    assert cross_tenant.status_code == 404


def test_editor_prefills_latest_tenant_cost_and_keeps_reasoned_override_revision_only(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "cost")
    _category, product, customer = _catalog(client, tenant_id, token)
    with session_factory() as db:
        tenant_product = db.get(TenantProduct, product["id"])
        assert tenant_product is not None
        supplier = TenantSupplier(tenant_id=tenant_id, name="Harbor Supplier")
        db.add(supplier)
        db.flush()
        tenant_product.preferred_supplier_id = supplier.id
        entry = TenantProductCostEntry(
            tenant_id=tenant_id,
            tenant_product_id=tenant_product.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("8.2000"),
            currency="USD",
            cost_basis=ProductPriceBasis.PIECE,
            pieces_per_box=12,
            effective_at=datetime.now(UTC),
            source_type="MANUAL",
            created_by_user_id=owner.id,
        )
        db.add(entry)
        db.commit()
        supplier_id = str(supplier.id)
        entry_id = str(entry.id)

    options = client.get(
        f"/api/v1/invoices/products/{product['id']}/cost-options",
        params={"tenant_id": tenant_id, "currency": "USD", "basis": "PIECE"},
        headers=_auth(token),
    )
    assert options.status_code == 200, options.text
    assert options.json()["options"] == [
        {
            "supplier_id": supplier_id,
            "supplier_name": "Harbor Supplier",
            "is_preferred": True,
            "product_cost_entry_id": entry_id,
            "unit_cost": "8.2000",
            "currency": "USD",
            "cost_basis": "PIECE",
            "pieces_per_box": 12,
            "effective_at": options.json()["options"][0]["effective_at"],
        }
    ]

    payload = _draft_payload(customer["id"], product["id"])
    payload["items"] = [payload["items"][0]]
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=payload,
    )
    assert created.status_code == 201, created.text
    item = created.json()["items"][0]
    assert item["supplier_id"] == supplier_id
    assert item["product_cost_entry_id"] == entry_id
    assert item["unit_cost"] == "8.2000"

    override_payload = _draft_payload(
        customer["id"],
        product["id"],
        predecessor_id=created.json()["current_revision_id"],
    )
    override_payload["items"] = [override_payload["items"][0]]
    override_item = override_payload["items"][0]
    assert isinstance(override_item, dict)
    override_item.update(
        {
            "supplier_id": supplier_id,
            "cost_override": "8.6000",
            "cost_basis": "PIECE",
            "cost_override_reason": "Updated supplier quote at the counter",
        }
    )
    updated = client.put(
        f"/api/v1/invoices/{created.json()['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=override_payload,
    )
    assert updated.status_code == 200, updated.text
    override = updated.json()["items"][0]
    assert override["unit_cost"] == "8.6000"
    assert override["is_cost_override"] is True
    assert override["product_cost_entry_id"] is None
    with session_factory() as db:
        assert db.scalar(
            select(TenantProductCostEntry).where(TenantProductCostEntry.id == entry_id)
        )
        old_items = list(
            db.scalars(
                select(InvoiceRevisionItem).where(
                    InvoiceRevisionItem.product_cost_entry_id == entry_id
                )
            )
        )
        assert len(old_items) == 1


def test_editor_rejects_mixed_currency_package_mismatch_and_unsafe_calculator(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, "validation")
    _category, product, customer = _catalog(client, tenant_id, token)
    payload = _draft_payload(customer["id"], product["id"])
    payload["currency"] = "LBP"
    mismatch = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=payload,
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "CURRENCY_MISMATCH"

    package_payload = _draft_payload(customer["id"], product["id"])
    first_item = package_payload["items"][0]
    assert isinstance(first_item, dict)
    first_item["price_basis"] = "BOX"
    first_item["pieces_per_box"] = 12
    package = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=package_payload,
    )
    assert package.status_code == 400
    assert package.json()["detail"]["code"] == "BARCODE_PACKAGE_MISMATCH"

    calculator = client.post(
        "/api/v1/invoices/calculator",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expression": "__import__('os')"},
    )
    assert calculator.status_code == 400
    assert calculator.json()["detail"]["code"] == "INVALID_CALCULATOR_EXPRESSION"
    valid_calculator = client.post(
        "/api/v1/invoices/calculator",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expression": "(٢ + ٣) / 2"},
    )
    assert valid_calculator.status_code == 200
    assert valid_calculator.json()["value"] == "2.5000"


def test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "confirm")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    assert created.status_code == 201, created.text
    invoice = created.json()

    confirm_body = {"expected_revision_id": invoice["current_revision_id"]}
    confirmed = client.post(
        f"/api/v1/invoices/{invoice['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=confirm_body,
    )
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["status"] == "CONFIRMED"
    assert result["official_invoice_number"].endswith("-000001")
    assert result["confirmed_at"] is not None

    replay = client.post(
        f"/api/v1/invoices/{invoice['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=confirm_body,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["official_invoice_number"] == result["official_invoice_number"]
    with session_factory() as db:
        charges = list(
            db.scalars(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.source_effect_key == f"invoice:{invoice['id']}:charge"
                )
            )
        )
        assert len(charges) == 1
        assert charges[0].signed_amount == Decimal("24.2500")
        assert db.scalar(select(InvoiceSequence.last_number)) == 1


def test_post_confirmation_revision_posts_exact_delta_and_keeps_old_balance_out_of_sales(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "revision")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    opening_at = datetime.now(UTC) - timedelta(days=5)
    opening = client.post(
        "/api/v1/customer-ledger/opening-balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "currency": "USD",
            "signed_amount": "10.0000",
            "effective_at": opening_at.isoformat(),
        },
    )
    assert opening.status_code == 201, opening.text
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    assert created.status_code == 201, created.text
    initial = created.json()
    assert initial["prior_balance"] == "10.0000"
    assert initial["net_sales"] == "24.2500"
    confirmed = client.post(
        f"/api/v1/invoices/{initial['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": initial["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text

    payload = _confirmable_payload(
        customer["id"],
        product["id"],
        predecessor_id=initial["current_revision_id"],
    )
    first_item = payload["items"][0]  # type: ignore[index]
    assert isinstance(first_item, dict)
    first_item["quantity_expression"] = "1"
    revised = client.put(
        f"/api/v1/invoices/{initial['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=payload,
    )
    assert revised.status_code == 200, revised.text
    current = revised.json()
    assert current["server_revision_number"] == 2
    assert current["prior_balance"] == "10.0000"
    assert current["net_sales"] == "11.7500"
    assert current["total_due"] == "21.7500"

    no_op_payload = _confirmable_payload(
        customer["id"],
        product["id"],
        predecessor_id=current["current_revision_id"],
    )
    no_op_item = no_op_payload["items"][0]  # type: ignore[index]
    assert isinstance(no_op_item, dict)
    no_op_item["quantity_expression"] = "1"
    no_op = client.put(
        f"/api/v1/invoices/{initial['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=no_op_payload,
    )
    assert no_op.status_code == 200, no_op.text

    history = client.get(
        f"/api/v1/invoices/{initial['id']}/history",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert history.status_code == 200, history.text
    revisions = history.json()["revisions"]
    assert [revision["server_revision_number"] for revision in revisions] == [3, 2, 1]
    assert [revision["ledger_delta"] for revision in revisions] == [
        "0.0000",
        "-12.5000",
        "24.2500",
    ]
    with session_factory() as db:
        effects = list(
            db.scalars(
                select(CustomerLedgerEntry)
                .where(CustomerLedgerEntry.source_id == initial["id"])
                .order_by(CustomerLedgerEntry.created_at)
            )
        )
        assert [effect.signed_amount for effect in effects] == [
            Decimal("24.2500"),
            Decimal("-12.5000"),
            Decimal("0.0000"),
        ]
        balance = db.scalar(
            select(func.sum(CustomerLedgerEntry.signed_amount)).where(
                CustomerLedgerEntry.customer_id == customer["id"],
                CustomerLedgerEntry.currency == "USD",
            )
        )
        assert balance == Decimal("21.7500")


def test_opening_balance_balance_api_overdue_alert_dedup_and_owner_security(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "debt")
    _category, _product, customer = _catalog(client, tenant_id, token)
    threshold = client.put(
        "/api/v1/customer-ledger/settings",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"customer_overdue_threshold_days": 30},
    )
    assert threshold.status_code == 200, threshold.text
    command = str(uuid4())
    payload = {
        "idempotency_key": command,
        "customer_id": customer["id"],
        "currency": "USD",
        "signed_amount": "75.0000",
        "effective_at": (datetime.now(UTC) - timedelta(days=40)).isoformat(),
        "note": "Balance carried into Tawzeevo",
    }
    opening = client.post(
        "/api/v1/customer-ledger/opening-balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=payload,
    )
    assert opening.status_code == 201, opening.text
    replay = client.post(
        "/api/v1/customer-ledger/opening-balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=payload,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == opening.json()["id"]

    balances = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert balances.status_code == 200, balances.text
    assert balances.json()["balances"] == [{"currency": "USD", "balance": "75.0000"}]
    first_debts = client.get(
        "/api/v1/customer-ledger/debts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    second_debts = client.get(
        "/api/v1/customer-ledger/debts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert first_debts.status_code == second_debts.status_code == 200
    debt = first_debts.json()["debts"][0]
    assert debt["is_overdue"] is True
    assert debt["overdue_age_days"] >= 40
    assert debt["alert_key"] == f"customer-overdue:{customer['id']}:USD"
    assert second_debts.json()["debts"][0]["alert_key"] == debt["alert_key"]
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CustomerLedgerEntry)
                .where(CustomerLedgerEntry.idempotency_key == command)
            )
            == 1
        )
        driver = User(
            first_name="Dina",
            last_name="Driver",
            email="driver-debt@example.com",
            phone="+96170111888",
            city="Beirut",
            age=28,
            type=SystemUserType.CLIENT,
            password_hash=hash_password(PASSWORD),
        )
        db.add(driver)
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=tenant_id,
                user_id=driver.id,
                role=TenantRole.DRIVER,
                is_active=True,
            )
        )
        db.commit()
        driver_email = driver.email
    denied = client.get(
        "/api/v1/customer-ledger/debts",
        params={"tenant_id": tenant_id},
        headers=_auth(_login(client, driver_email)),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "TENANT_OWNER_REQUIRED"


def test_invoice_sequence_is_serialized_per_tenant_and_year_under_concurrency(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "sequence")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    drafts: list[dict[str, object]] = []
    for _index in range(2):
        created = client.post(
            "/api/v1/invoices",
            params={"tenant_id": tenant_id},
            headers=_auth(token),
            json=_confirmable_payload(customer["id"], product["id"]),
        )
        assert created.status_code == 201, created.text
        drafts.append(created.json())

    def confirm(draft: dict[str, object]) -> str:
        with session_factory() as db:
            set_tenant_scope(db, UUID(tenant_id))
            result = confirm_invoice(
                db,
                UUID(tenant_id),
                owner.id,
                UUID(str(draft["id"])),
                UUID(str(draft["current_revision_id"])),
            )
            assert result.official_invoice_number is not None
            return result.official_invoice_number

    with ThreadPoolExecutor(max_workers=2) as pool:
        numbers = list(pool.map(confirm, drafts))
    current_year = datetime.now(UTC).year
    assert set(numbers) == {f"{current_year}-000001", f"{current_year}-000002"}
    with session_factory() as db:
        invoices = list(db.scalars(select(Invoice).where(Invoice.tenant_id == tenant_id)))
        assert len({invoice.official_invoice_number for invoice in invoices}) == 2
        assert db.scalar(select(InvoiceSequence.last_number)) == 2


def test_downward_confirmed_edit_releases_excess_allocation_without_mutating_payment(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "allocation-release")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    assert created.status_code == 201, created.text
    invoice = created.json()
    confirmed = client.post(
        f"/api/v1/invoices/{invoice['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": invoice["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    with session_factory() as db:
        charge = db.scalar(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.source_effect_key == f"invoice:{invoice['id']}:charge"
            )
        )
        assert charge is not None
        payment = Payment(
            tenant_id=tenant_id,
            customer_id=customer["id"],
            direction=PaymentDirection.CUSTOMER_RECEIPT,
            amount=Decimal("20.0000"),
            currency="USD",
            paid_at=datetime.now(UTC),
            recorded_by_user_id=owner.id,
            idempotency_key=uuid4(),
        )
        db.add(payment)
        db.flush()
        original_allocation = PaymentAllocation(
            tenant_id=tenant_id,
            payment_id=payment.id,
            customer_id=customer["id"],
            target_ledger_entry_id=charge.id,
            currency="USD",
            amount=Decimal("20.0000"),
            kind=AllocationKind.APPLY,
            created_by_user_id=owner.id,
            idempotency_key=uuid4(),
        )
        db.add(original_allocation)
        db.commit()
        payment_id = payment.id

    payload = _confirmable_payload(
        customer["id"], product["id"], predecessor_id=invoice["current_revision_id"]
    )
    line = payload["items"][0]  # type: ignore[index]
    assert isinstance(line, dict)
    line["quantity_expression"] = "1"
    revised = client.put(
        f"/api/v1/invoices/{invoice['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=payload,
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["net_sales"] == "11.7500"
    with session_factory() as db:
        allocations = list(
            db.scalars(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id))
        )
        effective = sum(
            (
                allocation.amount if allocation.kind == AllocationKind.APPLY else -allocation.amount
                for allocation in allocations
            ),
            Decimal("0"),
        )
        assert effective == Decimal("11.7500")
        assert len(allocations) == 3
        payment = db.get(Payment, payment_id)
        assert payment is not None
        assert payment.amount == Decimal("20.0000")


def test_receipt_fifo_owner_allocation_partial_multi_obligation_and_reversal_are_immutable(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "payments")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    confirmed_invoices: list[dict[str, object]] = []
    for _index in range(2):
        created = client.post(
            "/api/v1/invoices",
            params={"tenant_id": tenant_id},
            headers=_auth(token),
            json=_confirmable_payload(customer["id"], product["id"]),
        )
        assert created.status_code == 201, created.text
        confirmed = client.post(
            f"/api/v1/invoices/{created.json()['id']}/confirm",
            params={"tenant_id": tenant_id},
            headers=_auth(token),
            json={"expected_revision_id": created.json()["current_revision_id"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        confirmed_invoices.append(confirmed.json())

    obligations = client.get(
        f"/api/v1/payments/customers/{customer['id']}/obligations",
        params={"tenant_id": tenant_id, "currency": "USD"},
        headers=_auth(token),
    )
    assert obligations.status_code == 200, obligations.text
    before = obligations.json()["obligations"]
    assert len(before) == 2
    assert [row["source_id"] for row in before] == [invoice["id"] for invoice in confirmed_invoices]

    receipt_key = str(uuid4())
    receipt_payload = {
        "idempotency_key": receipt_key,
        "customer_id": customer["id"],
        "amount": "30.0000",
        "currency": "USD",
        "method": "CASH",
        "reference": "RCPT-100",
        "paid_at": datetime.now(UTC).isoformat(),
    }
    receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=receipt_payload,
    )
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["allocated_amount"] == "30.0000"
    assert receipt.json()["unallocated_amount"] == "0.0000"
    allocated_by_target = {
        row["target_ledger_entry_id"]: row["amount"] for row in receipt.json()["allocations"]
    }
    assert allocated_by_target == {
        before[0]["target_ledger_entry_id"]: before[0]["outstanding_amount"],
        before[1]["target_ledger_entry_id"]: "5.7500",
    }
    replay = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=receipt_payload,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == receipt.json()["id"]

    after_fifo = client.get(
        f"/api/v1/payments/customers/{customer['id']}/obligations",
        params={"tenant_id": tenant_id, "currency": "USD"},
        headers=_auth(token),
    ).json()["obligations"]
    assert len(after_fifo) == 1
    explicit = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
            "allocations": [
                {
                    "target_ledger_entry_id": after_fifo[0]["target_ledger_entry_id"],
                    "amount": "7.0000",
                }
            ],
        },
    )
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["allocated_amount"] == "7.0000"
    assert explicit.json()["unallocated_amount"] == "3.0000"

    reversal_payload = {
        "idempotency_key": str(uuid4()),
        "reason": "Cash receipt entered twice",
    }
    reversed_receipt = client.post(
        f"/api/v1/payments/{explicit.json()['id']}/reverse",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=reversal_payload,
    )
    assert reversed_receipt.status_code == 201, reversed_receipt.text
    assert reversed_receipt.json()["direction"] == "CUSTOMER_RECEIPT_REVERSAL"
    with session_factory() as db:
        payments = list(
            db.scalars(
                select(Payment).where(
                    Payment.tenant_id == tenant_id,
                    Payment.idempotency_key.in_([receipt_key, reversal_payload["idempotency_key"]]),
                )
            )
        )
        assert len(payments) == 2
        original = db.get(Payment, explicit.json()["id"])
        assert original is not None
        assert original.amount == Decimal("10.0000")
        assert original.direction == PaymentDirection.CUSTOMER_RECEIPT
        assert (
            db.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.idempotency_key == receipt_key)
            )
            == 1
        )


def test_customer_receipt_retries_one_command_and_a_new_intent_posts_again(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "payment-intent-replay")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    assert created.status_code == 201, created.text
    confirmed = client.post(
        f"/api/v1/invoices/{created.json()['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": created.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text

    first_key = str(uuid4())
    first_intent = {
        "idempotency_key": first_key,
        "customer_id": customer["id"],
        "amount": "10.0000",
        "currency": "USD",
        "method": "CASH",
        "reference": "one physical receipt",
        "paid_at": datetime.now(UTC).isoformat(),
    }
    attempts = [
        client.post(
            "/api/v1/payments/customer-receipts",
            params={"tenant_id": tenant_id},
            headers=_auth(token),
            json=first_intent,
        )
        for _attempt in range(3)
    ]
    assert all(attempt.status_code == 201 for attempt in attempts)
    assert len({attempt.json()["id"] for attempt in attempts}) == 1

    second_intent = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={**first_intent, "idempotency_key": str(uuid4())},
    )
    assert second_intent.status_code == 201, second_intent.text
    assert second_intent.json()["id"] != attempts[0].json()["id"]

    payment_ids = [attempts[0].json()["id"], second_intent.json()["id"]]
    with session_factory() as db:
        payments = list(
            db.scalars(
                select(Payment).where(
                    Payment.tenant_id == tenant_id,
                    Payment.id.in_(payment_ids),
                )
            )
        )
        effects = list(
            db.scalars(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.tenant_id == tenant_id,
                    CustomerLedgerEntry.source_type == "PAYMENT",
                    CustomerLedgerEntry.source_id.in_(payment_ids),
                )
            )
        )
        allocations = list(
            db.scalars(
                select(PaymentAllocation).where(
                    PaymentAllocation.tenant_id == tenant_id,
                    PaymentAllocation.payment_id.in_(payment_ids),
                )
            )
        )
        audit_count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "customer_receipt_recorded",
                AuditEvent.entity_id.in_(payment_ids),
            )
        )
        assert len(payments) == 2
        assert len(effects) == 2
        assert sum((effect.signed_amount for effect in effects), Decimal("0")) == Decimal(
            "-20.0000"
        )
        assert len(allocations) == 2
        assert sum((allocation.amount for allocation in allocations), Decimal("0")) == Decimal(
            "20.0000"
        )
        assert audit_count == 2

    balance = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert balance.status_code == 200, balance.text
    expected_balance = Decimal(confirmed.json()["net_sales"]) - Decimal("20.0000")
    assert Decimal(balance.json()["balances"][0]["balance"]) == expected_balance


def test_cancellation_preserves_payment_releases_credit_and_refund_ceiling_is_concurrent(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "cancel-refund")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    confirmed = client.post(
        f"/api/v1/invoices/{created.json()['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": created.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10.0000",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert receipt.status_code == 201, receipt.text
    cancel_payload = {"idempotency_key": str(uuid4()), "reason": "Owner approved cancellation"}
    cancelled = client.post(
        f"/api/v1/invoices/{created.json()['id']}/cancel",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=cancel_payload,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    replay = client.post(
        f"/api/v1/invoices/{created.json()['id']}/cancel",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=cancel_payload,
    )
    assert replay.status_code == 200
    balances = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    )
    assert balances.json()["balances"] == [{"currency": "USD", "balance": "-10.0000"}]
    assert (
        client.get(
            f"/api/v1/payments/customers/{customer['id']}/obligations",
            params={"tenant_id": tenant_id, "currency": "USD"},
            headers=_auth(token),
        ).json()["obligations"]
        == []
    )
    with session_factory() as db:
        payment = db.get(Payment, receipt.json()["id"])
        assert payment is not None
        assert payment.amount == Decimal("10.0000")
        rows = list(
            db.scalars(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id))
        )
        assert sum(
            (row.amount if row.kind == AllocationKind.APPLY else -row.amount for row in rows),
            Decimal("0"),
        ) == Decimal("0.0000")

    def concurrent_refund(index: int) -> str:
        with session_factory() as db:
            set_tenant_scope(db, UUID(tenant_id))
            try:
                result = record_customer_refund(
                    db,
                    UUID(tenant_id),
                    owner.id,
                    CustomerRefundRequest(
                        idempotency_key=uuid4(),
                        customer_id=UUID(str(customer["id"])),
                        amount=Decimal("7.0000"),
                        currency="USD",
                        paid_at=datetime.now(UTC) + timedelta(microseconds=index),
                    ),
                )
            except AppError as exc:
                return exc.code
            return str(result.customer_balance)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(concurrent_refund, range(2)))
    assert sorted(outcomes) == ["-3.0000", "REFUND_EXCEEDS_AVAILABLE_CREDIT"]
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.direction == PaymentDirection.CUSTOMER_REFUND)
            )
            == 1
        )
        balance = db.scalar(
            select(func.sum(CustomerLedgerEntry.signed_amount)).where(
                CustomerLedgerEntry.tenant_id == tenant_id,
                CustomerLedgerEntry.customer_id == customer["id"],
                CustomerLedgerEntry.currency == "USD",
            )
        )
        assert balance == Decimal("-3.0000")


def test_unconfirmed_cancellation_has_no_financial_effect(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "draft-cancel")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    cancelled = client.post(
        f"/api/v1/invoices/{created.json()['id']}/cancel",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"idempotency_key": str(uuid4()), "reason": "Draft abandoned"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CustomerLedgerEntry)
                .where(CustomerLedgerEntry.source_id == created.json()["id"])
            )
            == 0
        )


@pytest.mark.parametrize("receipt_amount", [None, "24.2500"])
def test_confirmed_cancellation_matrix_handles_unpaid_and_fully_paid_invoices(
    client: TestClient,
    session_factory: sessionmaker[Session],
    receipt_amount: str | None,
) -> None:
    suffix = "cancel-unpaid" if receipt_amount is None else "cancel-full"
    owner, tenant_id, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    confirmed = client.post(
        f"/api/v1/invoices/{created.json()['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": created.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    payment_id: str | None = None
    if receipt_amount is not None:
        receipt = client.post(
            "/api/v1/payments/customer-receipts",
            params={"tenant_id": tenant_id},
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "customer_id": customer["id"],
                "amount": receipt_amount,
                "currency": "USD",
                "paid_at": datetime.now(UTC).isoformat(),
            },
        )
        assert receipt.status_code == 201, receipt.text
        payment_id = receipt.json()["id"]
    cancelled = client.post(
        f"/api/v1/invoices/{created.json()['id']}/cancel",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"idempotency_key": str(uuid4()), "reason": "Matrix verification"},
    )
    assert cancelled.status_code == 200, cancelled.text
    balances = client.get(
        f"/api/v1/customer-ledger/customers/{customer['id']}/balances",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
    ).json()["balances"]
    expected_balance = "0.0000" if receipt_amount is None else f"-{receipt_amount}"
    assert balances == [{"currency": "USD", "balance": expected_balance}]
    if payment_id is not None:
        with session_factory() as db:
            payment = db.get(Payment, payment_id)
            assert payment is not None
            assert payment.amount == Decimal(receipt_amount)


def test_zero_value_confirmed_cancellation_keeps_an_explicit_immutable_reversal(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    owner, tenant_id, token = _owner_context(client, session_factory, "cancel-zero")
    _category, product, customer = _catalog(client, tenant_id, token)
    _attach_latest_cost(session_factory, owner, tenant_id, product["id"])
    created = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    confirmed = client.post(
        f"/api/v1/invoices/{created.json()['id']}/confirm",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"expected_revision_id": created.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    zero_payload = _confirmable_payload(
        customer["id"],
        product["id"],
        predecessor_id=confirmed.json()["current_revision_id"],
    )
    zero_payload["invoice_discount_expression"] = "25.25"
    revised = client.put(
        f"/api/v1/invoices/{created.json()['id']}",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json=zero_payload,
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["net_sales"] == "0.0000"
    cancelled = client.post(
        f"/api/v1/invoices/{created.json()['id']}/cancel",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"idempotency_key": str(uuid4()), "reason": "Zero-value closure"},
    )
    assert cancelled.status_code == 200, cancelled.text
    with session_factory() as db:
        reversal = db.scalar(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.source_effect_key
                == f"invoice:{created.json()['id']}:cancellation"
            )
        )
        assert reversal is not None
        assert reversal.entry_type == LedgerEntryType.INVOICE_REVERSAL
        assert reversal.signed_amount == Decimal("0.0000")
