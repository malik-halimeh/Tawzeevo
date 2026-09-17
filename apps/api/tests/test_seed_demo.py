from __future__ import annotations

import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.cli import seed_demo
from tawzeevo_api.models import (
    Category,
    Customer,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    SystemUserType,
    Tenant,
    TenantBarcode,
    TenantMembership,
    TenantProduct,
    TenantProductCostEntry,
    TenantRole,
    TenantStatus,
    TenantSupplier,
    User,
)
from tawzeevo_api.security import hash_password
from tawzeevo_api.services.invoice_finance import confirm_invoice


def create_owner_tenant(session_factory: sessionmaker[Session]) -> tuple[User, Tenant]:
    with session_factory() as db:
        owner = User(
            first_name="Demo",
            last_name="Owner",
            email="demo.owner@example.com",
            phone="+96170123456",
            city="Beirut",
            age=30,
            type=SystemUserType.CLIENT,
            password_hash=hash_password("correct horse battery staple"),
        )
        tenant = Tenant(
            name="Demo Distribution",
            status=TenantStatus.ACTIVE,
            activated_at=datetime.now(UTC),
        )
        db.add_all([owner, tenant])
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=tenant.id,
                user_id=owner.id,
                role=TenantRole.OWNER,
                is_active=True,
            )
        )
        db.commit()
        db.refresh(owner)
        db.refresh(tenant)
        db.expunge(owner)
        db.expunge(tenant)
        return owner, tenant


def test_demo_seed_creates_one_real_slice_and_rejects_replay(
    monkeypatch: object,
    capsys: object,
    session_factory: sessionmaker[Session],
) -> None:
    owner, tenant = create_owner_tenant(session_factory)
    arguments = [
        "seed-demo",
        "--owner-email",
        owner.email,
        "--tenant-id",
        str(tenant.id),
        "--customer-phone",
        "+961 70 555 444",
        "--currency",
        "usd",
    ]
    monkeypatch.setattr(sys, "argv", arguments)  # type: ignore[attr-defined]

    assert seed_demo.main(session_factory) == 0
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Customer)) == 1
        assert db.scalar(select(func.count()).select_from(Category)) == 1
        assert db.scalar(select(func.count()).select_from(TenantProduct)) == 1
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(InvoiceRevisionItem)) == 1
        invoice = db.scalar(select(Invoice))
        revision = db.scalar(select(InvoiceRevision))
        product = db.scalar(select(TenantProduct))
        assert invoice is not None and revision is not None
        assert invoice.current_revision_id == revision.id
        assert str(revision.subtotal) == "10.0000"
        barcode = db.scalar(select(TenantBarcode))
        assert product is not None and product.currency == "USD"
        assert barcode is not None and barcode.barcode == seed_demo.DEMO_BARCODE
        supplier = db.scalar(select(TenantSupplier))
        cost = db.scalar(select(TenantProductCostEntry))
        assert supplier is not None and cost is not None
        assert product.preferred_supplier_id == supplier.id
        assert cost.supplier_id == supplier.id and str(cost.unit_cost) == "1.7500"
        assert cost.currency == "USD"
    # The seeded draft is confirmable through the normal owner workflow (D-034 cost snapshot).
    with session_factory() as db:
        invoice = db.scalar(select(Invoice))
        assert invoice is not None
        confirmed = confirm_invoice(
            db, tenant.id, owner.id, invoice.id, invoice.current_revision_id
        )
        assert confirmed.status == "CONFIRMED"
        assert confirmed.official_invoice_number is not None

    assert seed_demo.main(session_factory) == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "DEMO_DATA_ALREADY_EXISTS" in output
