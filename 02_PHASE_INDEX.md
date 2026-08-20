# 02_PHASE_INDEX.md — Phase and Milestone Map

## Execution rule

Within a phase:
- one user `continue` = one milestone;
- the implementation agent stops after the milestone report;
- never cross a phase boundary on `continue`.

To enter a new phase, user explicitly says `Start Phase N`.

## Phase map

| Phase | File | Objective | Milestones | Start gate |
|---|---|---|---:|---|
| 1 | `PHASE_01.md` | Full program requirements + production foundation + platform tenant-approval/access control + presentation slice | 7 | repository instruction preflight |
| 2 | `PHASE_02.md` | tenant/customer/catalog/barcode/grade/pricing core | 5 | Phase 1 DoD |
| 3 | `PHASE_03.md` | invoice/ledger/payment/debt financial core | 6 | Gate C |
| 4 | `PHASE_04.md` | offline-first sync + Google encrypted backup | 6 | Gate D |
| 5 | `PHASE_05.md` | linked bilingual guest storefront | 5 | Gate E |
| 6 | `PHASE_06.md` | supplier price history + procurement + supplier debt | 5 | Phase 5 DoD |
| 7 | `PHASE_07.md` | owner/driver delivery operations + locations + route assistance | 4 | Gate F + routing provider approval |
| 8 | `PHASE_08.md` | analytics + lifetime stats + branding | 4 | Gate G |
| 9 | `PHASE_09.md` | production hardening + deployment + pilot | 6 | Phases 1–8 DoD |
| 10 | `PHASE_10.md` | optional season/month forecasting | 3 | reliable production-like historical data |

## Gate C — Financial core

Before Phase 3 code:
- `pricing-v1` locked/tested;
- money/currency/rounding locked;
- invoice source-of-truth locked;
- customer ledger locked;
- payment allocation locked;
- refund ceiling locked;
- cancellation/reversal semantics locked.

## Gate D — Offline

Before Phase 4 code:
- local schema/outbox protocol locked;
- idempotency/version/change cursor locked;
- bootstrap/tombstone/device registry locked;
- offline official-number authority locked;
- revocation behavior locked;
- Google OAuth scope/folder model approved by user before Google milestone.

## Gate E — Storefront/public access

Before Phase 5:
- order state machine locked;
- checkout idempotency locked;
- capability-token lifecycle locked;
- guest customer privacy rules locked;
- notification/reminder behavior locked.

## Gate F — Driver

Before Phase 7:
- delivery-task model locked;
- owner-as-operator and owner/driver assignee rules locked;
- driver least-privilege projection locked;
- single-owner/no-driver default behavior locked;
- location rules locked;
- current routing provider explicitly approved by user.

## Gate G — Analytics

Before Phase 8:
- metric definitions locked;
- revision/cancellation treatment locked;
- currency grouping locked;
- tenant timezone boundary locked.

## Phase-completion rule

A phase is complete only when its file's Definition of Done is satisfied and `03_IMPLEMENTATION_STATUS.md` contains validation evidence.

Do not mark a gate `PASSED` from intent alone. Required schema/tests/contracts must actually exist.
