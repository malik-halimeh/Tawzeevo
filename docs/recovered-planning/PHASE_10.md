# PHASE_10.md — Optional Seasonal / Monthly Best-Product Forecasting

## Phase objective
Implement the agreed tenant-specific "best products by season/month" prediction only after Tawzeevo has enough trustworthy production-like historical sales data.

Start with an explainable statistical baseline.

Machine learning is optional and must earn its complexity through measured improvement.

Do not add an LLM merely because this phase is described as AI/intelligence.

## Start gate
Phase 9 must be COMPLETE.

Do not begin forecasting until reliable historical data exists.

Verify:
- canonical invoice/revision history trustworthy;
- cancellations/reversals treated correctly;
- currencies separated;
- tenant timezone/calendar stable;
- product identity/history stable;
- minimum sample threshold can be defined from real data;
- a backtesting window exists.

If insufficient, return/represent `insufficient_data` rather than fabricate confidence.

---

# A. Scope

Per tenant analyze historical valid sales by:
- product;
- month;
- season;
- trend;
- recurrence.

Source only canonical confirmed, non-cancelled sales history.

Do not use:
- product views as sales;
- cancelled/non-valid sales;
- other tenant data;
- silently mixed currency;
- future information during backtesting.

---

# B. Statistical baseline

Build explainable deterministic/statistical baseline.

Output:
- monthly product performance;
- seasonal performance;
- trend;
- recurrence/stability;
- minimum-data check;
- confidence/strength with documented meaning;
- insufficient-data result.

Formula/model must be documented/versioned.

Do not return unexplained "AI score".

---

# C. Evaluation/backtesting

Use historical holdout/backtesting appropriate to available data.

Measure:
- ranking/top-product accuracy/relevance;
- stability;
- confidence meaning/calibration;
- interpretability;
- compute/operating cost;
- sparse/new-product behavior;
- cancellation/revision sensitivity.

Prevent future-data leakage.

Compare against simple baselines instead of declaring success without benchmark.

---

# D. ML — conditional only

Evaluate ML only if:
- baseline exists/tests;
- enough data;
- measurable baseline limitation.

Compare:
- backtesting accuracy;
- ranking quality;
- stability;
- interpretability;
- latency;
- complexity;
- cost.

If no material stable improvement, keep statistical baseline in production.

No generative AI/LLM.

Any external/hosted ML provider that materially changes cost/privacy/architecture requires explicit approval.

---

# E. Owner-facing behavior

Owner may view:
- predicted/top products for selected month/season;
- supporting historical evidence;
- trend/recurrence;
- confidence/strength;
- insufficient-data state;
- model/version explanation.

Use clear "forecast, not guarantee" language.

Never turn forecast into:
- automatic inventory;
- stock quantity;
- automatic supplier purchase;
- availability state.

---

# F. Tenant/privacy rules

- no cross-tenant prediction data exposure;
- tenant private history not used to train another tenant without explicit approval;
- platform admin does not automatically browse tenant forecasts/source sales;
- owner authorization/RLS required.

Any future global model is a new privacy/product decision.

---

# G. API/frontend scope

Add versioned forecasting service/API under current `/api/v1` conventions.

Backend owns calculation.

Store model/baseline version + reproducibility metadata.

Avoid redundant persistent forecast snapshots unless performance/audit need is justified.

Owner UI:
- month/season selector;
- ranking;
- confidence;
- historical evidence;
- insufficient state;
- model explanation;
- forecast disclaimer.

EN/AR/RTL/accessibility.
No driver/customer forecast exposure by default.

---

# H. Migration requirements

Prefer computed/service outputs.

Add tables only if justified for:
- model/version metadata;
- evaluation runs;
- cached results.

Every tenant-owned row tenant_id + RLS.

Never mutate sales history.

If schema added: zero + Phase 9 upgrade pass.

---

# I. Tests

## Data correctness
- only confirmed/non-cancelled canonical sales;
- revisions/cancellations correct;
- tenant timezone/month boundaries;
- currency separation;
- tenant isolation.

## Baseline
- deterministic;
- same data same output;
- sparse data insufficient;
- trend/season;
- new product;
- confidence documented/bounded.

## Backtesting
- no future leakage;
- benchmark comparison;
- repeatable.

## Optional ML
- baseline comparison;
- no adoption without measured improvement;
- fallback baseline;
- cost/latency captured.

## Authorization/UI
- owner only;
- driver/customer denied;
- platform admin no automatic tenant-private access;
- EN/AR/accessibility.

---

# J. Milestones

## P10-M1 — Historical dataset + statistical forecasting baseline
Implement data gate, canonical tenant/month/season dataset, deterministic baseline, trend/recurrence, minimum-sample/insufficient result, confidence semantics, owner API/UI.

Acceptance:
- reproducible;
- tenant/currency/timezone safe;
- insufficient path;
- no stock automation.

STOP.

## P10-M2 — Backtesting + optional ML comparison
Implement backtesting, simple benchmark, baseline metrics, and only if data supports it evaluate appropriate ML; compare accuracy/stability/interpretability/cost and record accept/reject decision.

Acceptance:
- no future leakage;
- evidence-based decision;
- baseline fallback;
- no LLM.

STOP.

## P10-M3 — Forecast UX, hardening, final optional-phase freeze
Complete owner UX, explanation/confidence, EN/AR/RTL/accessibility, performance/security/RLS, migrations if needed, evaluation docs, final audit.

Acceptance:
- DoD passes;
- prediction presented honestly;
- production method documented.

Mark Phase 10 COMPLETE and STOP.

---

# K. Definition of Done

- historical-data gate verified;
- statistical baseline exists;
- tenant-specific;
- month/season/trend/recurrence;
- confidence/insufficient semantics clear;
- no future leakage;
- ML only if demonstrably better;
- baseline retained if ML unjustified;
- no LLM added for branding;
- no inventory/automatic purchasing;
- authorization/RLS/EN/AR pass.

## Future ideas NOT mandatory
- general demand forecast;
- payment-delay prediction;
- advanced supplier scoring;
- conversational assistant.

Each requires explicit future approval.

First milestone to implement: **P10-M1 — Historical dataset + statistical forecasting baseline**
