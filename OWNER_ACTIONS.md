# OWNER_ACTIONS.md — decisions only you can make, with explanations

This is the single place to look when you wonder "what am I being asked to decide?". Each item has:
**what it is**, **the choices**, **what happens if you pick each one (consequences)**, and **my
recommendation**. Answer in chat with the item number and your choice (for example `B4: 2` or
`accept all candidates for C`). I record every answer in `04_DECISIONS.md`; nothing below is
implemented until you answer. Last updated 2026-09-17 (after the FA-009 closure).

Sections: A resolved/open housekeeping · B Phase 5 gate · C Phase 4 gate · D Phase 6 gate ·
E Phase 7 gate · F Phase 8 gate · G Phase 9 · H Phase 10 · I things to check yourself.

---

## A. Housekeeping

| # | Item | Status |
|---|---|---|
| A1 | FA-009 create-command identity | **Decided (option 1) → D-045, implemented and tested.** |
| A2 | Phase order | **Decided: normal order** — Phase 4 next, then Phase 5. Jira sprints reordered. |
| A3 | Push to GitHub | **Open — see below.** |

### A3 — pushing to GitHub

Your rule: push only if it does not include Markdown files about the AI workflow or decisions you
still need to take. **Every one of the 40+ local commits contains such files** (this file, the audit
register, the decision ledger, AGENTS.md changes), so a normal `git push` breaks your rule. Also
note: `AGENTS.md`, the phase files and `04_DECISIONS.md` are **already public** on GitHub since the
Phase 2 push (`dac294a`) — the mentor can already see them.

| Choice | What happens | Consequence |
|---|---|---|
| 1. Push everything as-is | `git push origin main` | Fast, honest history. The mentor can read the audit/decision docs if they browse. |
| 2. Remove private docs first, then push | One commit deletes `OWNER_ACTIONS.md`, `docs/audits/`, `docs/governance/`, `docs/recovered-planning/`, `AGENT_START_HERE.md`, `GUIDE_MANIFEST.md`, `IMPLEMENTATION_MASTER_PROMPT.md`, `docs/assurance/` from the tree (kept locally in an ignored folder) | Current tree looks clean, **but the files stay visible in older commits** on GitHub. Locally we lose nothing. |
| 3. Publish a clean branch (recommended if privacy matters) | Create an orphan branch `public` with one commit containing only code + user-facing docs; push it as a **new branch**; show the mentor that branch. `main` stays local. | Nothing private ever reaches GitHub. Downside: GitHub `main` stays stuck at Phase 2 and the public branch has no development history (one squashed commit per publish). |
| 4. Make the repository private | You flip it in GitHub settings, then option 1. | Simplest if the mentor gets collaborator access; but D-024 says the repo is public — you would be changing that decision. |

**Recommendation:** 3 if you want the mentor to see only the product; 1 if you don't mind them
seeing the working documents (they already can, partly). I will not push until you choose.

---

## B. Phase 5 gate (storefront) — decide before `Start Phase 5`

| # | Item | Status |
|---|---|---|
| B1 | Provisional checkout page | **Decided → D-046** |
| B2 | Storefront address / slug rules | **Decided → D-047** |
| B3 | Recommendation weights (purchase 10, view 1) | **Decided → D-048** |
| B4 | View de-duplication window | **Open — explanation below** |
| B5 | Anonymous interaction retention | **Open — explanation below** |
| B6 | Notifications / reminders | **Decided → D-049** |

### B4 — view de-duplication window

**What it is.** The storefront counts "views" of a product to power "recommended for you" lists.
Without a window, one shopper refreshing a product page 50 times counts as 50 views and can push
that product to the top of every recommendation. The window says: *the same anonymous session
viewing the same product again within N minutes counts once.*

| Choice | Consequence |
|---|---|
| 1. 30 minutes (spec candidate) | Balanced. A shopper comparing products back and forth counts once per product per half hour. Recommendations react to genuine browsing within the same day. |
| 2. 24 hours | Stronger anti-noise. One view per product per day per session; recommendations move slowly, better against a curious visitor "gaming" the list, worse at reflecting a busy shopping day. |
| 3. No window | Simplest code, but trivially skewed by refreshes; I do not recommend it. |

**Notes.** Sessions are pseudonymous (a random cookie id), never the phone number. Purchases are
never de-duplicated — each confirmed sale counts. The window is a storefront setting; changing it
later does not rewrite history. **Recommendation: 1 (30 minutes).**

### B5 — anonymous interaction retention

**What it is.** Raw view events (session id, product, timestamp) are personal-ish data even though
anonymous. Retention says how long the raw rows are kept before they are deleted or rolled up into
per-product totals.

| Choice | Consequence |
|---|---|
| 1. 90 days raw, then delete (spec candidate) | Recommendations use the last quarter of browsing. Small tables, low privacy exposure. Seasonal patterns older than a quarter are not visible to recommendations (they are still visible in *sales* analytics, which use invoices, not views). |
| 2. 90 days raw, then aggregate to monthly per-product counts | Keeps long-term "interest" trends for Phase 10 forecasting while dropping session ids. Slightly more code (an aggregation job). |
| 3. 365 days raw | Richer data, larger tables, longer privacy exposure; a data-protection reviewer would ask why. |

**Notes.** Purchase history is separate and is kept forever (it is financial history). Whatever you
pick, deletion runs as a scheduled job, which Phase 9 will monitor. **Recommendation: 2** if you
plan to use Phase 10 forecasting, otherwise 1.

---

## C. Phase 4 gate (offline sync + Google backup) — decide before `Start Phase 4`

C1–C3 are needed before the first milestone (P4-M1). C4–C6 are needed only before the Google
backup milestone (P4-M5), which is scheduled after the presentation.

### C1 — sync pull page size

**What it is.** When the app reconnects it downloads changes in pages. The page size is how many
change records come back per request.

| Choice | Consequence |
|---|---|
| 1. 500 per page (spec candidate) | Good balance on mobile networks in Lebanon: a page is a few hundred KB at most, a typical day syncs in 1–3 requests. |
| 2. 100 per page | More requests, more resilient on very poor connections, slower full bootstrap for a tenant with thousands of products. |
| 3. 2000 per page | Fewer requests, but a single failed request wastes more; larger memory spikes on old phones. |

**Recommendation: 1.** It can be tuned later without changing the protocol.

### C2 — tombstone retention

**What it is.** When something is deleted or archived on the server, a "tombstone" (a delete
marker) is kept so devices that were offline learn about the deletion when they reconnect. After the
retention period, a device that stayed offline longer must re-download everything (re-bootstrap)
instead of applying deltas.

| Choice | Consequence |
|---|---|
| 1. 90 days minimum (spec candidate) | A device offline for up to 3 months syncs incrementally; longer than that it re-bootstraps (safe, just slower). Tombstone table stays small. |
| 2. 30 days | Smaller table; a driver's phone left in a drawer for 5 weeks re-bootstraps. |
| 3. Keep forever | No re-bootstrap ever, but the table grows without bound. |

**Recommendation: 1.**

### C3 — offline lease length and device retirement

**What it is.** An offline lease is how long a registered device may keep working offline before it
must contact the server again to prove it is still allowed (membership not revoked, tenant not
suspended). Device retirement is when an unseen device is marked stale and must re-bootstrap.

| Choice | Consequence |
|---|---|
| 1. Lease 24 h, retire after 90 days unseen (spec candidate) | A van without signal keeps working for a full day; after that the app shows "reconnect to continue" for changes (reading stays possible). Revoked drivers lose access within a day at most. |
| 2. Lease 72 h | Friendlier for multi-day trips; a revoked driver could keep creating offline invoices for up to 3 days (they are rejected on reconnect, but the driver sees no warning meanwhile). |
| 3. Lease 8 h | Tighter security; annoying on long rural days. |

**Notes.** The lease is never authentication — the real access token still expires every 15 minutes
online and refreshes silently. **Recommendation: 1.**

### C4 — Google OAuth scope and Drive folder model (needed before P4-M5)

**What it is.** To back up encrypted tenant data to the owner's Google Drive, the app asks Google
for permission. The *scope* is how much of the owner's Drive the app may touch.

| Choice | Consequence |
|---|---|
| 1. `drive.file` — only files the app created itself, in a folder the app creates (recommended) | Least privilege: the app cannot see the owner's personal files. Google's verification for this scope is light. The owner can see and delete the backup folder in their Drive. |
| 2. `drive.appdata` — hidden app-data folder | Even narrower and invisible to the owner in Drive UI; the owner cannot manually download or inspect a backup, which hurts the "I can see my data" story. |
| 3. Full `drive` scope | Not acceptable: gives the app access to everything; Google requires a security assessment. |

**Folder model:** one folder per tenant named `Tawzeevo Backup – <business name>` under the owner's
Drive, created by the app. **Recommendation: 1 with that folder model.** You will also need to
create a Google Cloud project and an OAuth client ID (I'll write the exact steps when Phase 4 starts).

### C5 — backup schedule and retention

| Choice | Consequence |
|---|---|
| 1. Daily encrypted backup; keep 30 daily + 12 monthly (candidate) | Roughly 42 files per tenant; a year of restore points; storage in the owner's Drive quota (small: a busy tenant is a few MB per backup). |
| 2. Weekly; keep 12 | Less Drive usage, up to a week of data lost in a disaster. |
| 3. Daily; keep 7 | Minimal storage, only one week of restore points. |

**Notes.** Backups are a disaster-recovery copy; PostgreSQL stays the live database.
**Recommendation: 1.**

### C6 — encryption key management

**What it is.** Backups are encrypted before they reach Google. Each tenant gets its own data key
(DEK); the DEK is itself wrapped by a master key (KEK) the app controls. The question is where the
KEK lives.

| Choice | Consequence |
|---|---|
| 1. KEK stored as a secret in the hosting provider (Render environment secret), one per environment | No extra cost; rotation is a manual runbook. If the Render secret is lost, all backups become unreadable — so the KEK must also be stored in your password manager. |
| 2. Cloud KMS (Google Cloud KMS or AWS KMS) | Proper key rotation and audit; small monthly cost and one more provider account. |
| 3. Owner-held passphrase (each owner types a passphrase to restore) | Zero server secrets; if the owner forgets it the backup is gone forever; support burden. |

**Recommendation: 1 now (with the KEK copied into your password manager), 2 in Phase 9 if you go
to real production with many tenants.**

---

## D. Phase 6 gate (suppliers & procurement) — decide before `Start Phase 6`

### D1 — procurement list lifecycle

**What it is.** A daily procurement list is built from confirmed customer demand. The lifecycle
defines when a list is "done".

| Choice | Consequence |
|---|---|
| 1. `OPEN → PARTIALLY_PURCHASED → COMPLETE / CANCELLED`; remaining quantities can be **carried forward** to the next day's list; an owner can **waive** a line (mark it "not needed") with a reason (recommended) | Nothing is silently lost: a line is either bought, carried forward, or explicitly waived. Slightly more UI (a waive button + reason). |
| 2. Same states, no waive: unbought lines must be carried forward or the list cancelled | Simpler, but a list with one line the owner decided not to buy can never be completed cleanly. |

**Recommendation: 1.**

### D2 — quote vs actual-purchase cost provenance

**What it is.** The Phase 3 cost entries have a `source_type` (`MANUAL`, `OWNER_OVERRIDE`). Phase 6
adds supplier quotes and actual purchases. The decision is how they map onto the existing cost table
so historical invoices are never affected.

| Choice | Consequence |
|---|---|
| 1. Add two source types, `QUOTE` and `ACTUAL_PURCHASE`, on the **same** cost-entry table; invoice entry preloads the latest **actual purchase** first, then the latest quote, then manual (recommended) | One history table (D-034 kept), best-supplier ranking can prefer real prices over quotes, no rewriting of past invoices. |
| 2. Separate `supplier_quotes` table, only actual purchases go into cost entries | Cleaner separation but two places to look for "what does this cost", and ranking needs to join both. |

**Recommendation: 1.**

---

## E. Phase 7 gate (delivery & routes) — decide before `Start Phase 7`

### E1 — online routing / geocoding provider (must be an explicit decision)

**What it is.** Offline, the app orders stops by a simple nearest-neighbour heuristic (no provider).
Online, a provider can give road distances and a better order. Lebanon coverage matters.

| Choice | Consequence |
|---|---|
| 1. OpenRouteService (free tier, OpenStreetMap data) | Free up to ~2,000 requests/day; OSM coverage of Lebanon roads is decent in cities, thinner in villages; no billing account needed. Good for a pilot. |
| 2. Google Maps Platform (Routes + Geocoding) | Best Lebanon coverage and address search; needs a billing account with a credit card; ~200 USD/month free credit covers a small pilot; privacy terms must be reviewed (customer addresses sent to Google). |
| 3. Mapbox | Middle ground; free tier 100k requests/month; OSM-based; needs an account. |
| 4. No online provider in Phase 7 (offline heuristic + manual reorder only) | Zero cost and zero privacy exposure; the "route" feature is weaker in the demo. |

**Recommendation: 1 for the pilot, revisit 2 if address geocoding quality is not enough.**
Whatever you pick, the code goes through an adapter with a fallback to the offline heuristic.

### E2 — delivery task terminal states and reopening

| Choice | Consequence |
|---|---|
| 1. `ASSIGNED → COMPLETED / CANCELLED`, terminal, no reopen (spec candidate) | Simple and auditable; a mistaken "completed" needs a new task created by the owner. |
| 2. Allow owner "reopen" with a reason | More flexible; adds an audit event and one more state transition. |

**Recommendation: 1 for Phase 7; add 2 only if the pilot asks for it.**

### E3 — customer location precedence

**What it is.** A customer can have a location from three sources: typed manually, geocoded from the
address, or captured by GPS at the door. Which one wins?

| Choice | Consequence |
|---|---|
| 1. Confirmed (operator-approved) location always wins; among unconfirmed, GPS with accuracy better than 50 m beats geocoded beats manual; a worse reading never overwrites a better one (recommended) | Predictable; the driver's confirmed pin at the door becomes the truth. |
| 2. Latest reading wins | Simple but a bad GPS reading in a garage overwrites a good pin. |

**Recommendation: 1.**

---

## F. Phase 8 gate (analytics & branding) — decide before `Start Phase 8`

These are formulas; I propose exact definitions so nothing is "invented" later.

| # | Metric | Proposed definition | Note |
|---|---|---|---|
| F1 | invoiced_sales | Sum of current `net_sales` of CONFIRMED, non-cancelled invoices, by currency | Old balance excluded. |
| F2 | customer_receipts | Sum of non-reversed customer receipts (payments minus reversals), by currency | Refunds shown separately. |
| F3 | customer_outstanding / supplier_payable | Positive ledger balances by currency | Credits shown separately, never netted across parties. |
| F4 | historical_gross_profit | Σ over confirmed revision lines of `(effective_unit_price − unit_cost_snapshot) × quantity`, same currency only | Uses the sale-time cost snapshot (D-031/D-034); a line with a missing snapshot is reported as "uncovered", never estimated. |
| F5 | cost coverage | `covered lines / all confirmed lines` per period | Profit is shown with its coverage %. |
| F6 | periods | Per invoice, last 30 days, last 90 days, last 365 days, on the tenant's calendar (Asia/Beirut), events dated by confirmation / edit acceptance / cancellation approval | Matches D-040 style. |
| F7 | lifetime stats | total purchased, total receipts, outstanding, largest and average invoice, count, first/latest purchase, average days between purchases, top 5 products and categories by quantity and value, current grade, late-payment count (receipts allocated after the overdue threshold) | Duplicates never merged. |
| F8 | small-cohort privacy for public stats | Any public aggregate over fewer than 5 tenants or 20 customers shows "insufficient data" | Protects individual businesses. |

**Recommendation: accept F1–F8 as written.** Say `accept all candidates for F` and I will record them.

---

## G. Phase 9 (production hardening) — decide before the named milestones

| # | Item | Choices and consequences | Recommendation |
|---|---|---|---|
| G1 | Is password recovery mandatory for launch? (before P9-M1) | Yes: forgot-password email flow with single-use tokens and session invalidation — needs an email provider (SendGrid/Mailgun free tiers). No: admins reset passwords manually; simpler, not acceptable for real customers. | **Yes**, with a transactional email provider on its free tier (that provider choice is a separate small decision). |
| G2 | Performance targets (before P9-M3) | Accept the spec candidates (phone/barcode lookup p95 < 250 ms, CRUD < 400 ms, checkout < 750 ms, sync 100 ops < 2.5 s, 5xx < 1 %) or relax them | **Accept**; they are measurable on Render's free tier with a small load test. |
| G3 | Background worker (before P9-M4) | Render background worker (paid ~7 USD/month) vs. running jobs inside the API process on a timer (free, less isolated) | **In-process scheduler for the pilot**, worker when paying customers exist. |
| G4 | Object storage for product images | Local disk on Render is wiped on deploy. Options: Cloudflare R2 (free 10 GB), Backblaze B2 (free 10 GB), AWS S3 (paid), Supabase Storage (free 1 GB) | **Cloudflare R2** — S3-compatible, generous free tier. |
| G5 | Staging environment | A second Render service + a Supabase branch database (free) vs. none | **Yes, one staging pair**; it protects the demo database from experiments. |

---

## H. Phase 10 (forecasting) — decide at its gate

| # | Item | Proposal | Consequence |
|---|---|---|---|
| H1 | Minimum data to forecast | At least 6 months of confirmed sales and 20 sales of a product | Below this the UI shows "not enough data" instead of a guess. |
| H2 | Season definition | Lebanon calendar: Winter Dec–Feb, Spring Mar–May, Summer Jun–Aug, Autumn Sep–Nov; plus month-level view | Simple and explainable. |
| H3 | Confidence meaning | "Strength" = how consistently a product ranked in the top N in the same month of previous years (0–100 %) | Honest, no black box. |
| H4 | Backtest window | Hold out the last 3 months and check whether the top-5 prediction matched actual top-5 | Reported in the UI as "last check accuracy". |

**Recommendation: accept H1–H4 when the time comes.**

---

## I. Things to check yourself

- Revoke or rotate the Jira API token you shared (id.atlassian.com → Security → API tokens).
- Keep `docs/documents/` (BRD, ERD, DDD, FDD) out of the public repo — it is git-ignored.
- Before Phase 4's Google milestone: create a Google Cloud project and an OAuth client (I will give
  the exact click-path when we get there).
