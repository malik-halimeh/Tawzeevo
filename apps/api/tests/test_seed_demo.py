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
    InvoiceItem,
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantProduct,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.security import hash_password


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
        assert db.scalar(select(func.count()).select_from(InvoiceItem)) == 1
        invoice = db.scalar(select(Invoice))
        product = db.scalar(select(TenantProduct))
        assert invoice is not None and str(invoice.subtotal) == "10.0000"
        assert product is not None and product.currency == "USD"
        assert product.barcode == seed_demo.DEMO_BARCODE

    assert seed_demo.main(session_factory) == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "DEMO_DATA_ALREADY_EXISTS" in output
