# OWNER_ACTIONS.md — what only the owner can decide or unblock

Plain-language list of things that need **you**. Work continues around them; nothing here is
started until you answer. When you answer, reply in chat (for example: "A1: option 2") and the
decision will be recorded in `04_DECISIONS.md` for you. Last updated 2026-09-17 (Sprint 1).

## A. Decisions needed now (before or during Sprint 1/2)

| # | Question | Options (recommended first) | Why it matters |
|---|---|---|---|
| A1 | **FA-009 — how should a repeated "create draft invoice" command be recognised?** | 1. Same `client_command_id` per tenant returns the same invoice header (recommended, matches Phase 4 sync). 2. Keep today's behaviour (each retry makes a new draft). 3. Something else you prefer. | Without this, a client retry after a lost response can leave two draft invoices. Not money-affecting, but it matters for the offline sync work in Phase 4. |
| A2 | **Confirm the phase order Phase 3 → Phase 5 (storefront) → Phase 4 (offline)** | 1. Yes, storefront first (recommended for the 25 Sept presentation). 2. No, keep the spec order 4 then 5. | Sprints 2 and 3 in Jira assume option 1. Recorded as D-045 once you confirm. |
| A3 | **Push the 33 local commits to GitHub** | Say "push" whenever you are ready. | Everything is committed locally and neutral (no AI attribution). GitHub is still at the end of Phase 2. |

## B. Gate decisions for Phase 5 (needed before Sprint 2 starts, 20 Sept)

Each row is a `REVIEW_REQUIRED` item in `PHASE_05.md`. Candidate values are what the spec suggests;
say "accept all candidates" if you are happy with them.

| # | Item | Candidate | Notes |
|---|---|---|---|
| B1 | How a guest sees their order right after checkout (the "provisional" page) | A separate short-lived provisional link tied to the checkout session, distinct from the confirmed-invoice link (D-042 untouched). | Must not weaken the confirmed-link rules. |
| B2 | Tenant storefront address format | `https://<platform>/<tenant-slug>/…`, slug 3–50 chars, lowercase, unique; renames create a redirect and are audited. | |
| B3 | Recommendation weights | purchase = 10, view = 1 | Purchase must stay heavier than view. |
| B4 | View de-duplication window | One view per session per product per 30 minutes | |
| B5 | Anonymous interaction retention | 90 days, then delete or aggregate | |
| B6 | Owner notification and reminder behaviour | In-app notification, one per checkout; delivery reminders as job records, no external SMS/email provider yet | Adding a provider would be a new dependency decision. |

## C. Gate decisions for Phase 4 (needed before Sprint 3 starts, 23 Sept)

| # | Item | Candidate | Notes |
|---|---|---|---|
| C1 | Sync pull page size | 500 changes per page | |
| C2 | Tombstone retention | 90 days minimum | |
| C3 | Offline lease length / device retirement | 24 hours; stale devices re-bootstrap | |
| C4 | **Google OAuth scope and Drive folder model** | Narrowest scope that lets the app write to its own app folder (`drive.file` or `drive.appdata`); one folder per tenant | **Required before the Google backup milestone (P4-M5). Never guessed.** |
| C5 | Backup schedule and retention | Daily encrypted backup, keep 30 daily + 12 monthly | |
| C6 | Key management for backups | Per-tenant data key wrapped by an environment key stored in the hosting provider's secret store | Production provider for the secret store is your call. |

## D. Later gates (no action yet — listed so nothing is forgotten)

- **Phase 6:** procurement state names and carry-forward rules; quote vs actual-purchase mapping.
- **Phase 7:** the online routing/geocoding provider (Lebanon coverage and price) — must be an explicit decision; delivery-task terminal/reopen rules; location precedence.
- **Phase 8:** exact metric formulas, periods, profit coverage rule, lifetime statistics, small-cohort privacy threshold.
- **Phase 9:** is password recovery mandatory for launch; performance targets; worker / object storage / staging providers.
- **Phase 10:** minimum sample size, season definition, confidence meaning, backtest window.

## E. Things you may want to check yourself

- Delete or rotate the Jira API token you shared (id.atlassian.com → Security → API tokens). A fresh one is needed only when Jira is updated again.
- The `docs/documents/` folder (BRD, ERD, DDD, FDD) is ignored by git on purpose; keep it out of the public repo.
