# P3-M5 baseline remediation and checkpoint boundary

Quality gate: PASS (2026-09-05), independently reproduced in a clean checkout on 2026-09-06.
This is baseline remediation only; P3-M6 remains NOT_STARTED.
The user authorized this pass after the acceptance gate failed on whole-backend Ruff checks and
the absence of a complete, clean checkpoint. No application behavior is changed by remediation.

## Governing rules and migration treatment

- `AGENTS.md`: never rewrite applied shared migrations; passing relevant tests and touched-code
  checks, accurate evidence and no unrelated features are required for milestone completion.
- `PHASE_03.md` sections M/N and P3-M5 govern immutable migration history and acceptance.
- Root `README.md` documents whole-backend `ruff check apps/api` and `ruff format --check apps/api`.
- No repository rule requires a broad migration exclusion. None is introduced.
- Git history before remediation ends at `dac294a542941e9c0f9aab5826160e75fb8301c3` (Phase 2 core).
  Neither 0009 nor 0010 was committed there, so Git alone cannot prove a production release.
  Existing milestone records and the disposable local database at head `20260827_0011` prove
  their use in the applied/tested migration chain. No production database or deployment was queried.
  Both files are therefore preserved under the existing immutability rule, without claiming a release.

Exact treatment in `apps/api/pyproject.toml`:

1. Ignore only `I001` for `alembic/versions/20260827_0009_invoice_item_line_order.py`.
2. Exclude exactly that file and `alembic/versions/20260827_0010_financial_confirmation_debt.py`
   from formatting. All other selected lint rules still apply to both files.
3. Every other migration and all new migrations retain full selected lint/format checks.
4. `tests/test_immutable_migration_files.py` fingerprints both files. Only Git's LF/CRLF
   conversion is normalized; every other content/whitespace change fails. Do not refresh hashes
   or expand exclusions to silence failures. Corrections to schema behavior require a new migration.

Canonical SHA-256 fingerprints:

| Revision | SHA-256 (LF-normalized) |
|---|---|
| 0009 | `c1c8d1757639e21c77307987844e75e2c68721540c8843800eb04a8be2794d1c` |
| 0010 | `cf9bf734ebcc0f542f3e63096abf3d98879bff85b5d8d22d7654b30003916c8c` |

## Classification of every original dirty path

Original status: 25 tracked modifications + 52 untracked files = 77 paths. Nothing was staged.
Classification uses imports, migration dependencies, tests, phase requirements and prior evidence,
not timestamps. Shared files are included whole when earlier changes are required by P3-M5.

| Group | Count | Disposition |
|---|---:|---|
| A — P3-M5 implementation/integration | 17 | Include |
| B — Earlier required implementation/dependency/data prerequisites | 32 | Include |
| C — Required migration chain | 5 | Include unchanged |
| D — Current authoritative/reproduction/evidence documentation | 14 | Include |
| E — Separate future/study work | 9 | Preserve outside baseline |
| F — Generated/local files among the original 77 | 0 | None to stage |

Ignored local environments, secrets, caches, build outputs, coverage files and local runtime data
remain ignored and untouched; they are not baseline inputs. The committed catalog quality report
is a required public-safe evidence artifact, not a disposable test output.

| Group | Original path | Classification evidence |
|---|---|---|
| B | `.env.example` | P3-M2 deterministic fuzzy-match threshold used by invoice entry; example contains only non-secret defaults/placeholders. |
| D | `03_IMPLEMENTATION_STATUS.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `04_DECISIONS.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `AGENTS.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `GUIDE_MANIFEST.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `README.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `RUN_TESTS.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `apps/api/README.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| A | `apps/api/pyproject.toml` | API package/template metadata and baseline quality configuration; required to install/check the accepted app. |
| B | `apps/api/tawzeevo_api/cli/seed_demo.py` | P3-M1 canonical revision/model compatibility (plus catalog provenance); current routes/seeding depend on it. |
| B | `apps/api/tawzeevo_api/config.py` | P3-M2 deterministic fuzzy-match threshold used by invoice entry; example contains only non-secret defaults/placeholders. |
| A | `apps/api/tawzeevo_api/main.py` | Shared integration required to mount/render P3-M5 and retain earlier invoice flows; include the complete current file. |
| B | `apps/api/tawzeevo_api/models.py` | P3-M1 canonical revision/model compatibility (plus catalog provenance); current routes/seeding depend on it. |
| B | `apps/api/tawzeevo_api/services/cash_van.py` | P3-M1 canonical revision/model compatibility (plus catalog provenance); current routes/seeding depend on it. |
| B | `apps/api/tests/conftest.py` | Earlier financial/catalog regression or fixture adaptation required by the current immutable schema; no new skipped tests. |
| B | `apps/api/tests/test_cash_van.py` | Earlier financial/catalog regression or fixture adaptation required by the current immutable schema; no new skipped tests. |
| B | `apps/api/tests/test_hardening.py` | Earlier financial/catalog regression or fixture adaptation required by the current immutable schema; no new skipped tests. |
| B | `apps/api/tests/test_seed_demo.py` | Earlier financial/catalog regression or fixture adaptation required by the current immutable schema; no new skipped tests. |
| B | `apps/operations-web/src/api/types.ts` | P3-M2–M4 editor dependencies: typed responses, workspace integration, EN/AR labels or editor regression. |
| B | `apps/operations-web/src/components/TenantWorkspace.tsx` | P3-M2–M4 editor dependencies: typed responses, workspace integration, EN/AR labels or editor regression. |
| B | `apps/operations-web/src/i18n.ts` | P3-M2–M4 editor dependencies: typed responses, workspace integration, EN/AR labels or editor regression. |
| A | `apps/operations-web/src/styles.css` | Shared integration required to mount/render P3-M5 and retain earlier invoice flows; include the complete current file. |
| E | `docs/Tawzeevo-Python-FastAPI-Study-Journey.html` | Separate study-document redesign; no runtime dependency. Preserve outside baseline. |
| D | `docs/contracts/financial-invariants.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `docs/folder-responsibilities.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| D | `PHASE_03.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |
| E | `PHASE_04.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `PHASE_05.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `PHASE_06.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `PHASE_07.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `PHASE_08.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `PHASE_09.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `PHASE_10.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| E | `REMAINING_PHASE_GUIDE_MANIFEST.md` | Future-phase specification/provenance; excluded from the through-P3-M5 checkpoint, preserved for later work. |
| C | `apps/api/alembic/versions/20260826_0007_catalog_import_provenance.py` | P2-M5 provenance migration; mandatory predecessor of Phase 3 schema. |
| C | `apps/api/alembic/versions/20260826_0008_financial_core_schema.py` | P3-M1–M4 immutable financial migration chain; Alembic head 0011 and migration tests require it. |
| C | `apps/api/alembic/versions/20260827_0009_invoice_item_line_order.py` | P3-M1–M4 immutable financial migration chain; Alembic head 0011 and migration tests require it. |
| C | `apps/api/alembic/versions/20260827_0010_financial_confirmation_debt.py` | P3-M1–M4 immutable financial migration chain; Alembic head 0011 and migration tests require it. |
| C | `apps/api/alembic/versions/20260827_0011_zero_invoice_cancellation.py` | P3-M1–M4 immutable financial migration chain; Alembic head 0011 and migration tests require it. |
| B | `apps/api/tawzeevo_api/cli/import_master_catalog.py` | Uncommitted P2-M5 importer/provenance prerequisite; required by CLI, README, catalog and database regression tests. |
| A | `apps/api/tawzeevo_api/public_invoice_security.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| B | `apps/api/tawzeevo_api/routes/customer_ledger.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/routes/invoices.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/routes/payments.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| A | `apps/api/tawzeevo_api/routes/public_invoices.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/api/tawzeevo_api/routes/supplier_ledger.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| B | `apps/api/tawzeevo_api/schemas/customer_ledger.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/schemas/invoice_editor.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/schemas/payments.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| A | `apps/api/tawzeevo_api/schemas/public_invoices.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/api/tawzeevo_api/schemas/supplier_ledger.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| B | `apps/api/tawzeevo_api/services/catalog_import.py` | Uncommitted P2-M5 importer/provenance prerequisite; required by CLI, README, catalog and database regression tests. |
| B | `apps/api/tawzeevo_api/services/customer_ledger.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/services/invoice_editor.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/services/invoice_finance.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| B | `apps/api/tawzeevo_api/services/payments.py` | P3-M2–M4 invoice/ledger/payment route-schema-service prerequisite; imported directly by current main.py or P3-M5 services. |
| A | `apps/api/tawzeevo_api/services/public_invoices.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/api/tawzeevo_api/services/supplier_ledger.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/api/tawzeevo_api/templates/public_invoice.html` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| B | `apps/api/tests/test_catalog_import.py` | Uncommitted P2-M5 importer/provenance prerequisite; required by CLI, README, catalog and database regression tests. |
| B | `apps/api/tests/test_financial_schema.py` | Earlier financial/catalog regression or fixture adaptation required by the current immutable schema; no new skipped tests. |
| B | `apps/api/tests/test_invoice_editor.py` | Earlier financial/catalog regression or fixture adaptation required by the current immutable schema; no new skipped tests. |
| A | `apps/api/tests/test_public_invoices.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/api/tests/test_supplier_ledger.py` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| B | `apps/api/uv.lock` | Existing locked backend dependency resolution used by documented uv test workflow; reproducibility input, not a cache. |
| B | `apps/operations-web/src/components/InvoiceEditor.test.tsx` | P3-M2–M4 editor dependencies: typed responses, workspace integration, EN/AR labels or editor regression. |
| A | `apps/operations-web/src/components/InvoiceEditor.tsx` | Shared integration required to mount/render P3-M5 and retain earlier invoice flows; include the complete current file. |
| A | `apps/operations-web/src/components/InvoiceSharing.test.tsx` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/operations-web/src/components/InvoiceSharing.tsx` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| A | `apps/operations-web/src/components/PublicInvoicePage.test.ts` | P3-M5 capability, privacy, supplier foundation or direct acceptance test; PHASE_03 section J / P3-M5. |
| B | `data/master-catalog/README.md` | D-032 licensed catalog snapshot, attribution or quality report; importer/test_catalog_import require this bundle. |
| B | `data/master-catalog/open-food-facts-lebanon-v1.json` | D-032 licensed catalog snapshot, attribution or quality report; importer/test_catalog_import require this bundle. |
| B | `data/master-catalog/open-food-facts-lebanon-v1.quality.json` | D-032 licensed catalog snapshot, attribution or quality report; importer/test_catalog_import require this bundle. |
| D | `docs/phase-2/demo-guide.md` | Mandatory frozen Phase 2 completion evidence required by AGENTS.md; not future implementation. |
| D | `docs/phase-2/requirements-audit.md` | Mandatory frozen Phase 2 completion evidence required by AGENTS.md; not future implementation. |
| D | `docs/phase-2/test-report.md` | Mandatory frozen Phase 2 completion evidence required by AGENTS.md; not future implementation. |
| D | `docs/phase-3/p3-m5.md` | Current rules, approved decisions, phase specification, status, reproduction or milestone evidence. |

## Preservation and checkpoint boundary

All nine group-E paths are preserved in local stash
`9050d544791b5e22d15c2ff1a1acdbd503b40418`, named
`Preserve future phase guides and study-document changes outside P3-M5 baseline`.
Saved content was verified against pre-stash SHA-256 fingerprints for all nine paths, normalizing
only Git line endings. The original committed study document remains in the baseline; its separate
redesign is not included. Future phase guides must be restored before later phase work needs them.

After the audits, restore deliberately in the original repository with:

```powershell
git stash apply 9050d544791b5e22d15c2ff1a1acdbd503b40418
```

Use `apply`, not `pop`, to retain the safety copy. Inspect any conflicts; do not force restoration.
This stash is local and is not included in the audit commit or published. Keep it until the separate
work is safely committed elsewhere. No reset, checkout-discard, clean or blanket staging was used.

The baseline includes 68 original paths plus the migration guard test and this report (70 changed
paths relative to old HEAD). It intentionally includes uncommitted P2-M5/P3-M1–M4 prerequisites;
it does not pretend to be an isolated P3-M5-only patch. No application/test source outside the new
content guard is rewritten during remediation. Documentation/configuration changes are limited to
quality-gate consistency, status, classification and reproduction evidence.

## Continuity flags retained, not decided

The preceding gate flagged exact rate-limit/capacity settings, tenant-prefix/fragment transport,
FastAPI-served public HTML, multiple active links, draft/cancelled sharing and supplier overpayment
policy for later continuity review. This checkpoint records existing tested behavior; it does not
approve undocumented policy or claim a complete architecture/security/financial audit. Deployed
proxy logs, distributed limiting and phase-wide browser/accessibility audits remain outside this pass.

## Validation and reproducibility

Executed on 2026-09-05 from the repository root with the existing local development environment:

| Command | Result |
|---|---|
| `.\.venv\Scripts\python -m ruff check .\apps\api` | PASS; whole backend, exact historical treatment above |
| `.\.venv\Scripts\python -m ruff format --check .\apps\api` | PASS; 80 files, two exact historical exclusions |
| `.\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api` | PASS; 52 source files |
| `.\.venv\Scripts\python -m alembic -c .\apps\api\alembic.ini upgrade head` | PASS; head 20260827_0011 |
| `.\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80` | PASS; 126 tests, no skips/failures, 92.29% statement coverage |
| `.\.venv\Scripts\alembic -c .\apps\api\alembic.ini check` | PASS; no new upgrade operations |
| `npm run check` | PASS; ESLint, TypeScript, 34 tests, production build (210 modules) |
| `git diff --check` and tracked/nonignored conflict-marker scan | PASS; no markers or unmerged index entries |

The backend suite includes from-zero and Phase 2 legacy upgrade/downgrade/re-upgrade regressions,
P3-M5 lifecycle/privacy/RLS/concurrency tests, and both new migration-content guards. The pre-existing
database-fixture skip is unchanged and was not triggered. No newly skipped/disabled tests or code
TODO/FIXME/HACK markers were introduced. All 64 original included files outside the four initial
remediation targets were byte-for-byte unchanged before documentation/status finalization, including
all five migration files. The historical migrations remain byte-for-byte unchanged throughout.

Existing non-blocking advisories: Vite chunk size and Starlette/httpx deprecation. No coverage
threshold was lowered. These results establish the candidate gate, not P3-M6 completion.

No production database, message sending, deployment, dependency upgrade or Git push is authorized here.

### Clean-checkout reproduction — 2026-09-06

The implementation checkpoint is `1097593b00c1773e70d1df783fa6dca4322f3ed5`,
`Complete implementation through P3-M5 with guarded migration checks`.
A separate detached worktree was created from that exact commit. Neither the original `.env`,
virtual environment, nor `node_modules` was copied. The existing Python interpreter was reused
only to create a new isolated environment; an import-path check confirmed application imports
resolved inside the clean checkout.

Dependency installation used these commands, without regenerating either lockfile:

```powershell
# In the clean checkout's apps/api directory; Python 3.13.2 was already installed.
uv --system-certs sync --locked --extra dev --python 'C:/Users/malik/Desktop/DigitalHub/Tawzeevo/.venv/Scripts/python.exe' --no-python-downloads
# In the clean checkout root.
npm ci
```

Environment: Windows, Python 3.13.2, Node 22.21.0, npm 11.14.1, PostgreSQL 18.4;
locked Ruff 0.16.4. `DATABASE_URL` and `TEST_DATABASE_URL` were set only for each test process,
to the same disposable loopback database. No `.env` or secret file was required. The database
was restarted with explicit loopback host/test port after the default-port startup failed;
this was local infrastructure setup, not a migration or application failure.

Exact checks from the clean checkout root:

| Command | Result |
|---|---|
| `.\apps\api\.venv\Scripts\python -m ruff check .\apps\api` | PASS |
| `.\apps\api\.venv\Scripts\python -m ruff format --check .\apps\api` | PASS; 80 files, same two guarded exclusions |
| `.\apps\api\.venv\Scripts\python -m mypy --config-file .\apps\api\pyproject.toml .\apps\api\tawzeevo_api` | PASS; 52 source files |
| `.\apps\api\.venv\Scripts\python -m alembic -c .\apps\api\alembic.ini upgrade head` | PASS; 20260827_0011 |
| `.\apps\api\.venv\Scripts\python -m pytest .\apps\api\tests -q --cov=tawzeevo_api --cov-report=term-missing --cov-fail-under=80` | PASS; 126 passed, 0 failed/skipped, 92.29% coverage; 230.61 seconds |
| `.\apps\api\.venv\Scripts\python -m alembic -c .\apps\api\alembic.ini check` | PASS; no new upgrade operations |
| `npm run check` | PASS; ESLint, TypeScript, 34 tests / 5 files, production build / 210 modules |
| `git diff dac294a542941e9c0f9aab5826160e75fb8301c3 HEAD --check` | PASS; full checkpoint diff |
| `git status --porcelain=v1`, `git diff --exit-code`, `git diff --cached --exit-code` | PASS; clean working tree and index after installation/checks |

The suite again exercised the migration regressions and both immutable-content guards. No test
was skipped. Conflict-marker/unmerged-entry scans and introduced skip/TODO/FIXME/HACK inspection
were clean. Dependency locks were unchanged. Both frontend asset hashes match the original
candidate build (`index-D3_2u385.js`, `index-BpCvA8Wu.css`).

Non-blocking warnings are recorded rather than suppressed: the existing Vite chunk-size and
Starlette/httpx deprecation advisories, plus PyJWT's short development-placeholder warning in
this `.env`-free run (406 total backend warnings). `Settings.validate_production_security`
already rejects the placeholder and secrets shorter than 32 bytes in production; its tests pass.
This is not evidence of a production secret defect, and no credentials were examined or changed.

The final checkpoint adds only documentation recording this reproduction. Application, tests,
migrations, configuration, catalog data and dependency locks must remain identical to the tested
implementation commit. The final full commit SHA is emitted in the handoff rather than embedded
in its own contents. The nine-path preservation stash remains intact. P3-M6 and larger audits
have not started.
