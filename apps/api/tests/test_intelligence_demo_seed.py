"""D-089 intelligence demo-history seed: one run on a dedicated empty tenant drives every owner
intelligence view (priorities, inactivity, anomalies, cash flow) through the real API, the history
reconciles with the ledger and analytics services, currencies stay apart, the guards refuse a
non-empty tenant, a wrong confirmation name and production, and a failure leaves nothing behind."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_delivery_tasks import _get
from test_invoice_editor import _owner_context

from tawzeevo_api.cli.seed_intelligence_demo import main, seed_atomically
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    SupplierLedgerEntry,
    TenantFinancialSettings,
    TenantProduct,
)
from tawzeevo_api.services import analytics, payments
from tawzeevo_api.services.customer_ledger import customer_balances
from tawzeevo_api.services.intelligence.features import customer_features

REQUIRED_ANOMALIES = {
    "SALES_PERIOD_HIGH",
    "CUSTOMER_INVOICE_VALUE_HIGH",
    "BACKDATED_RECEIPT_LARGE",
    "OVERDUE_THRESHOLD_CROSSED",
    "LINE_PRICE_BELOW_SNAPSHOT_COST",
    "SUPPLIER_PAYABLE_JUMP",
    "REFUND_SPIKE",
}


def _group(body, currency):
    return next(g for g in body["groups"] if g["currency"] == currency)


def _by_name(items):
    return {item["customer_name"]: item for item in items}


def test_demo_seed_drives_every_intelligence_view(client, session_factory, test_engine):
    owner, tenant, token = _owner_context(client, session_factory, "intdemo")
    tenant_id = UUID(tenant)
    result = seed_atomically(
        test_engine,
        owner_email=owner.email,
        tenant_id=tenant_id,
        confirm_tenant_name="Route intdemo",
    )
    assert result.counts["customers"] == 10 and result.counts["products"] == 10
    assert result.counts["invoices_cancelled"] == 2 and result.counts["customer_refunds"] == 3
    assert result.counts["receipt_reversals"] == 2 and result.counts["delivery_tasks"] == 5

    bodies = {}
    for name in ("priorities", "inactivity", "anomalies", "cash-flow"):
        response = _get(client, tenant, token, f"/api/v1/intelligence/{name}")
        assert response.status_code == 200, (name, response.text)
        bodies[name] = response.json()

    # ---- daily priorities, ranked per currency
    priorities = bodies["priorities"]
    assert [g["currency"] for g in priorities["groups"]] == ["LBP", "USD"]
    usd = _by_name(_group(priorities, "USD")["items"])
    tyre = usd["Tyre Fresh Foods"]
    assert tyre["band"] == "HIGH" and tyre["suggested_action_code"] == "COLLECT_OVERDUE"
    assert "OLD_OVERDUE_BALANCE" in {r["code"] for r in tyre["reasons"]}
    byblos = usd["Byblos Grocery"]
    assert byblos["inactivity_status"] in {"AT_RISK", "LAPSED"}
    assert byblos["suggested_action_code"] == "REACTIVATE_CUSTOMER"
    assert usd["Zahle Wholesale"]["suggested_action_code"] == "COLLECT_OVERDUE"
    batroun = usd["Batroun Bakery"]
    assert "ACTIVITY_DOWN_VS_90D" in {r["code"] for r in batroun["reasons"]}
    assert batroun["suggested_action_code"] == "CHECK_ACTIVITY_DECLINE"
    jounieh = usd["Jounieh Minimart"]
    assert {"RECENT_CANCELLATIONS", "RECENT_REVERSALS"} <= {r["code"] for r in jounieh["reasons"]}
    assert jounieh["suggested_action_code"] == "REVIEW_RECENT_FRICTION"
    assert usd["Mount Lebanon Market"]["band"] == "LOW"
    lbp = _group(priorities, "LBP")["items"]
    assert [i["customer_name"] for i in lbp] == ["Hamra Café"]
    assert Decimal(lbp[0]["outstanding_balance"]) > 0

    # ---- inactivity risk
    inactivity = {
        (g["currency"], i["customer_name"]): i["status"]
        for g in bodies["inactivity"]["groups"]
        for i in g["items"]
    }
    assert inactivity[("USD", "Saida Corner Shop")] == "INSUFFICIENT_HISTORY"
    assert inactivity[("USD", "Byblos Grocery")] in {"AT_RISK", "LAPSED"}
    assert inactivity[("USD", "Mount Lebanon Market")] == "NORMAL"
    assert inactivity[("USD", "Tyre Fresh Foods")] == "WATCH"
    assert inactivity[("USD", "دكان الأرز")] == "NORMAL"
    assert inactivity[("LBP", "Hamra Café")] == "NORMAL"

    # ---- anomalies: every required family, attributed to the intended subject
    usd_anomalies = _group(bodies["anomalies"], "USD")
    assert usd_anomalies["insufficient_history"] == []
    types = defaultdict(list)
    for item in usd_anomalies["items"]:
        types[item["type"]].append(item)
    assert set(types) >= REQUIRED_ANOMALIES, sorted(types)
    assert types["SALES_PERIOD_HIGH"][0]["severity"] == "HIGH"
    assert [a["details"]["customer_name"] for a in types["CUSTOMER_INVOICE_VALUE_HIGH"]] == [
        "Tripoli Traders"
    ]
    assert [a["details"]["customer_name"] for a in types["BACKDATED_RECEIPT_LARGE"]] == [
        "Batroun Bakery"
    ]
    backdated = types["BACKDATED_RECEIPT_LARGE"][0]
    assert backdated["details"]["days_recorded_after_payment_date"] == 20
    crossed = types["OVERDUE_THRESHOLD_CROSSED"]
    assert [a["details"]["customer_name"] for a in crossed] == ["Zahle Wholesale"]
    assert crossed[0]["details"]["days_past_threshold"] == 4
    assert [a["details"]["customer_name"] for a in types["LINE_PRICE_BELOW_SNAPSHOT_COST"]] == [
        "Jounieh Minimart"
    ]
    # LBP has enough history to be evaluated and nothing unusual: no LBP group at all.
    assert [g["currency"] for g in bodies["anomalies"]["groups"]] == ["USD"]

    # ---- cash flow: per currency, never combined
    cash = {c["currency"]: c for c in bodies["cash-flow"]["currencies"]}
    assert list(cash) == ["LBP", "USD"]
    assert bodies["cash-flow"]["overdue_threshold_days"] == 30
    usd_cash, lbp_cash = cash["USD"], cash["LBP"]
    assert Decimal(usd_cash["position"]["overdue_receivables"]) > 0
    assert usd_cash["position"]["overdue_customer_count"] == 2
    buckets = {b["bucket"]: b for b in usd_cash["ageing"] if Decimal(b["amount"]) > 0}
    assert {"AGE_0_30", "AGE_31_60", "AGE_61_90"} <= set(buckets)
    assert sum(Decimal(b["amount"]) for b in usd_cash["ageing"]) == Decimal(
        usd_cash["position"]["customer_receivables"]
    )
    assert usd_cash["planned_collections"]["task_count"] >= 3
    assert lbp_cash["planned_collections"]["task_count"] == 1
    assert Decimal(usd_cash["position"]["supplier_payables"]) > 0
    assert Decimal(usd_cash["historical_flow"]["supplier_payments"]) > 0
    assert Decimal(usd_cash["historical_flow"]["customer_refunds"]) > 0

    # ---- reconciliation with the ledger and analytics services
    with session_factory() as db:
        features = customer_features(db, tenant_id)
        overview = analytics.overview(db, tenant_id, "90d")
        positive: dict[str, Decimal] = defaultdict(Decimal)
        for row in features:
            ledger = {
                b.currency: b.balance
                for b in customer_balances(db, tenant_id, row.customer_id).balances
            }
            assert row.balance == ledger[row.currency], row.customer_name
            positive[row.currency] += row.outstanding_balance
        outstanding = {r.currency: r.amount for r in overview.customer_outstanding}
        credit = {r.currency: r.amount for r in overview.customer_credit}
        hamra = next(r for r in features if r.customer_name == "Hamra Café")
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "intelligence_demo_history_seeded",
            )
        )
    assert outstanding == dict(positive) and credit == {}
    assert Decimal(usd_cash["position"]["customer_receivables"]) == outstanding["USD"]
    assert Decimal(lbp_cash["position"]["customer_receivables"]) == outstanding["LBP"]
    assert outstanding["LBP"] == hamra.balance  # the only LBP debtor; never added to USD
    assert audit is not None and audit.details["synthetic"] is True

    # ---- guards
    def run(**overrides):
        arguments = {
            "owner_email": owner.email,
            "tenant_id": tenant_id,
            "confirm_tenant_name": "Route intdemo",
            **overrides,
        }
        with pytest.raises(AppError) as refused:
            seed_atomically(test_engine, **arguments)
        return refused.value.code

    assert run() == "TENANT_NOT_EMPTY"
    assert run(confirm_tenant_name="route intdemo") == "TENANT_NAME_MISMATCH"
    assert run(app_env="production") == "PRODUCTION_REFUSED"
    assert run(owner_email="nobody@example.com") == "OWNER_NOT_FOUND"
    argv = ["--owner-email", owner.email, "--tenant-id", tenant, "--confirm-tenant-name", "Nope"]
    assert main(argv, engine=test_engine) == 1


def test_a_failure_midway_leaves_the_tenant_untouched(
    client, session_factory, test_engine, monkeypatch
):
    owner, tenant, _token = _owner_context(client, session_factory, "intdemofail")
    tenant_id = UUID(tenant)

    def fail(*_args, **_kwargs):
        raise AppError(409, "INJECTED_FAILURE", "Injected failure")

    monkeypatch.setattr(payments, "record_customer_receipt", fail)
    with pytest.raises(AppError, match="Injected failure"):
        seed_atomically(
            test_engine,
            owner_email=owner.email,
            tenant_id=tenant_id,
            confirm_tenant_name="Route intdemofail",
        )
    with session_factory() as db:
        for model in (
            Customer,
            TenantProduct,
            Invoice,
            CustomerLedgerEntry,
            SupplierLedgerEntry,
            TenantFinancialSettings,
        ):
            count = db.scalar(
                select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
            )
            assert count == 0, model.__tablename__
