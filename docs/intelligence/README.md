# Owner intelligence (D-089, D-091)

Owner-only insight built on Tawzeevo's own records: who needs attention today, whose buying
rhythm slipped, what was unusual this week, where cash stands — a read-only business assistant
that answers questions from those same figures, and short written explanations inside the
screens (a customer brief, one unusual change, the cash position).

- Owner setup still needed: [AI_SETUP_REQUIRED.md](AI_SETUP_REQUIRED.md) (only the assistant needs it)
- Demo data and how to see each layer work: [AI_DATA_POPULATION_PLAN.md](AI_DATA_POPULATION_PLAN.md)
- Authority: `04_DECISIONS.md` D-089 (scope, provider, data egress), D-091 (contextual
  explanations), D-066 (currencies),
  D-040 (overdue), D-067 (no margin), D-086 (forecasting stays Phase 10)

## Architecture

```text
canonical records (invoices at current revision, customer/supplier ledgers, payments,
delivery tasks, settings)  — RLS + tenant from the server-side TenantContext
        │
        ▼
services/intelligence/features.py   one pass per customer + currency (no N+1), fixed as_of
        ├── customers.py   priorities (score parts + reasons + action) · inactivity bands
        ├── anomalies.py   7-day block vs ≤ 8 prior blocks, median/MAD, 10 rule families
        ├── cashflow.py    position · ageing · period history · labelled delivery projection
        └── products.py    top products (line sales) · catalog lookup
        │
        ├──▶ routes/intelligence.py   GET priorities | inactivity | anomalies | cash-flow
        │                              (require_tenant_owner; drivers/admin/public refused)
        │
        └──▶ copilot/tools.py   9 read-only typed tools (pydantic-validated arguments, no SQL,
                 │              no writes, tenant bound server-side)
             copilot/privacy.py  customer names → conversation-scoped HMAC references before
                 │              egress; resolved back inside Tawzeevo
             copilot/service.py  system prompt, tool loop (≤ COPILOT_MAX_TOOL_ROUNDS),
                 │              rate limit 30/h per owner, figure check → unverified_numbers
             copilot/provider.py Groq chat completions over httpx, timeout, short error codes,
                                  nothing logged
             POST /copilot/query · GET /copilot/status
             copilot/explain.py  contextual explanations (D-091): facts assembled by the
                                  server for one customer, one unusual change or the cash
                                  position → same mask → ONE provider call, no tools →
                                  same figure check, errors and hourly limit
             POST /explain {kind: customer | anomaly | cash}
```

- **Deterministic truth stays outside the model.** Every amount, band, score and anomaly is
  computed by Python services from canonical rows. The model only chooses which read-only tool
  to call and phrases the answer; answer figures that appear in no tool result are returned as
  `unverified_numbers` and flagged in the UI.
- **Computed on request, nothing stored:** no intelligence tables, no migration, no background
  job, no stored conversations (the client keeps its history and sends it back in reference form).
- **Contextual explanations reuse the assistant, not a second stack.** `explain.py` shares the
  provider adapter, provider checks and error mapping (`open_request`, `call_provider`), the
  privacy mask and reference resolution (`resolve_answer`), the figure check and the shared
  rules of the system prompt (`SHARED_RULES`). The difference: the server chooses the facts,
  so the model is offered no tools and cannot fetch anything else. The facts use plain names
  (what customers owe now, what was paid to suppliers in the period, the age range in words,
  the rule an anomaly applies) because real-model runs showed neutral API field names and code
  names being misread or quoted.
- **On demand only.** Each explanation is written when the owner presses its button: never on
  opening a record, never in the background. The browser keeps it for the session per exact
  context (business, customer or change or period, language), so reopening the same record
  shows it again without a new call; any other context starts unasked. Explanations and
  assistant questions share one hourly limit per owner (`COPILOT_REQUESTS_PER_HOUR`, 30).
- **No speculative infrastructure:** no vector store, embeddings, agent framework, streaming or
  second provider — none of the features need them.

## Feature inventory

| Capability | Kind | API | Where the owner sees it | Tests |
|---|---|---|---|---|
| Daily customer priorities | Deterministic | `GET /api/v1/intelligence/priorities` | Work › Today's priorities; Customers › Needs attention › Priorities; customer record › Signals | `test_intelligence_customers.py`, `test_intelligence_api.py`, `IntelligencePanel.test.tsx`, `App.test.tsx`, E2E |
| Buying rhythm (inactivity) | Deterministic | `GET …/inactivity` | Customers › Needs attention › Buying rhythm; customer record › Signals | `test_intelligence_customers.py`, `test_intelligence_features.py`, `IntelligencePanel.test.tsx` |
| Unusual changes (anomalies) | Deterministic | `GET …/anomalies` | Analytics › Unusual changes this week; count on Work | `test_intelligence_anomalies.py`, `IntelligencePanel.test.tsx`, E2E |
| Cash position and ageing | Deterministic (projection labelled) | `GET …/cash-flow` | Analytics › Cash position and ageing (shares the Analytics period) | `test_intelligence_cashflow.py`, `IntelligencePanel.test.tsx`, E2E |
| Top products / catalog lookup | Deterministic | via assistant tools | Assistant answers | `test_intelligence_products.py`, `test_intelligence_copilot.py` |
| Business assistant | Hybrid (LLM over deterministic tools) | `GET …/copilot/status`, `POST …/copilot/query` | More › Assistant | `test_intelligence_copilot.py`, `test_intelligence_copilot_provider.py`, `CopilotPanel.test.tsx`, E2E (provider stubbed in the browser) |
| Customer brief | Hybrid (LLM wording of the customer's priorities, rhythm, balances, history, unusual changes) | `POST …/explain` `{kind: "customer", customer_id}` | Customers › record › Signals › **Summarize this customer** | `test_intelligence_explain.py`, `Explanation.test.tsx`, E2E |
| Unusual-change explanation | Hybrid (LLM wording of one anomaly, the rule it applies, the invoice and customer balance it concerns) | `POST …/explain` `{kind: "anomaly", currency, index, type, subject_id}` (409 `ANOMALY_CHANGED` if the list moved on) | Analytics › Unusual changes › each row › **Explain this change** | `test_intelligence_explain.py`, `Explanation.test.tsx`, E2E |
| Cash-position summary | Hybrid (LLM wording of the position, ageing, period flows and planned deliveries; server-computed overdue share; no forecast) | `POST …/explain` `{kind: "cash", period, currency?}` | Analytics › Cash position and ageing › **Summarize the cash position** (follows the period selector) | `test_intelligence_explain.py`, `Explanation.test.tsx`, E2E |
| Demo history | Tooling | CLI `tawzeevo_api.cli.seed_intelligence_demo` | — | `test_intelligence_demo_seed.py` |

Security coverage: `test_route_authorization.py` and `test_security_matrix.py` include every
intelligence route (owner allowed; another business's owner, driver, platform admin and anonymous
refused); `test_intelligence_api.py` checks no phone/address/token keys and no other tenant's data
in responses and that GETs write nothing; the assistant tests check the provider payload carries
no names, phones, addresses or tokens, tool arguments cannot choose a tenant, malformed provider
replies and timeouts end in controlled errors, and no tool can write. The explanation tests
(`test_intelligence_explain.py`) add: another business's or an unknown customer is not found and
nothing is sent; drivers and anonymous callers are refused; only the three typed contexts exist
(no free prompt, unknown fields refused); a changed anomaly is refused with 409; names, phones
and ids never reach the provider; a product name written like an instruction travels only inside
the JSON facts and leaves the system prompt unchanged; invented figures are flagged; currencies
stay separate; Arabic is requested when the screen is Arabic; nothing is written.

## Placement (UX audit)

| Feature | Where | Why there | Complements | Unnatural navigation? | Duplication | Effect on order → invoice → payment → delivery | When unavailable |
|---|---|---|---|---|---|---|---|
| Today's priorities | Work, under the day summary, top 3 only | Work is the owner's first screen; "who to call" is a start-of-day decision | The day's stops | No; each row opens the customer | Same data as Customers list, but only the top 3 | None; stops follow directly, driver never sees it | Quiet inline error with retry; stops unaffected |
| Needs attention (priorities + buying rhythm) | Customers, below the phone search | Customers had no list; this gives the owner a reason-ordered list to act from | Phone search, customer record | No | Buying rhythm is a second view of the same list, not a copy | None | Inline error + retry; search still works |
| Signals | Customer record, below identity and actions | The "why" belongs with the person you are about to call | Edit, storefront link, Invoices › Balances link | No | Reasons only; balances stay in Invoices | None | Inline error + retry |
| Cash position and ageing | Analytics, right after Current state, same period selector | Money position is an analytics question; sharing the period avoids a second control | Current state (overview) | No | Does not repeat "owed"/"owed to suppliers" figures except as the base of "overdue of owed" | None | Inline error + retry; rest of Analytics loads |
| Unusual changes | Analytics, after cash; count + link on Work | Reviewing deviations is a weekly analysis task; the Work line only signals that something exists | Event flow | Rows open the invoice or customer | None | None | Inline error + retry |
| Business assistant | Its own owner section under More (rail on desktop) | Free-form questions are not tied to one record; a section keeps it out of the core workflow (plan: owner section, not a floating chat) | Links back to Customers and Analytics | Customer names in answers open the record | Answers restate figures shown elsewhere, by design, with sources | None; read-only | "Not switched on" panel pointing to the deterministic screens; provider errors explained with "Ask again" |
| Customer brief | End of the customer record's Signals | The owner is about to call or visit this customer; the "why" and one point to raise belong with the phone number | Signals (calculated), Edit, Storefront link | No: it is on the record | Restates the signals in two to four lines, under them, never instead of them | None; read-only | One muted line ("A written summary appears here once the business assistant is switched on"); failures show inside it with Try again |
| Unusual-change explanation | Under each unusual change, beside "Open the invoice/customer" | Explaining a flag is the next question after reading it; the row keeps the link to the record | The calculated row (value, usual value, severity) | No: inline, no navigation | Adds the rule and a next check to the row; nothing duplicated elsewhere | None | The Explain action is hidden; the list is unchanged. A changed list is reported and reloaded |
| Cash-position summary | Top of Analytics › Cash position and ageing | Interpreting the per-currency cards is the reason to be on that section | The cash cards and ageing tables | No | A short reading of the cards below it, keyed to the selected period | None | Same one-line note as the brief; the cards stay |

All surfaces: English and Arabic (RTL), amounts isolated left-to-right with their currency, no
forecast/probability/fraud wording, phone layouts verified at 390 px, drivers never receive them.

## Verification (2026-09-25; D-091 on branch `feature/contextual-ai`)

See `03_IMPLEMENTATION_STATUS.md` › Owner intelligence for the recorded results. Reproduce:

```text
# backend (disposable PostgreSQL only; never the hosted database)
cd apps/api && python -m pytest -q
python -m ruff check . && python -m ruff format --check . && python -m mypy tawzeevo_api
# operations web
cd apps/operations-web && npm run lint && npm run typecheck && npm test && npm run build
# E2E (API without GROQ_API_KEY on :8011, Vite on :5173, storefront on :3000)
npx playwright test
```

The only step not verifiable without the owner is a real provider answer
([AI_SETUP_REQUIRED.md](AI_SETUP_REQUIRED.md) § 7).

## Known limits (unchanged by this work, recorded in D-089)

- Delivery "amount to collect" ignores later invoice adjustments; shown only as a labelled
  projection.
- No late-payment proxy (FIFO allocation and backdating make it unprovable), no customer margin,
  no product net revenue — top products are line sales before invoice-level adjustments.
- Rate limiting is per API process (in memory), as for the public-invoice limiter.
