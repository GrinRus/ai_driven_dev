# Post-W93 Cleanup Report

- Timestamp: `2026-02-06T09:04:26Z`
- Branch: `wave-93`
- Head commit (pre-cleanup-commit): `49cb55562a122f496901ab442bf9141d12c78231`

## Executive summary

- Baseline before cleanup was green (`ci-lint`, `smoke-workflow`, `pytest`).
- Applied only additive/compatible cleanups: cache hygiene, tools-inventory entrypoint consolidation, and maintainers-reports clarity docs.
- Deprecated review shims were verified as behavior-preserving; no target behavior changes applied.
- Post-cleanup validation is green for all required checks.

## Baseline and validation

- Baseline logs: `dev/reports/cleanup/logs/20260206T085635Z`
  - `ci-lint`: exit `0` (pass)
  - `smoke-workflow`: exit `0` (pass)
  - `pytest`: exit `0` (pass)
- Post-cleanup logs: `dev/reports/cleanup/logs/20260206T090202Z`
  - `ci-lint`: exit `0` (pass)
  - `smoke-workflow`: exit `0` (pass)
  - `pytest`: exit `0` (pass)

## What changed (safe cleanups)

- Updated `.gitignore`: added `.mypy_cache/`, `.ruff_cache/`, `.DS_Store` (existing cache ignores retained).
- Removed local generated cache artifacts: `hooks/__pycache__/` (untracked runtime byproducts).
- Consolidated inventory entrypoint duplication: `tools/tools-inventory.sh` now thinly delegates to `tools/tools-inventory.py` and preserves exit code via `os.execv`.
- Improved canonical inventory module bootstrap: `tools/tools_inventory.py` now supports direct invocation (`python3 tools/tools_inventory.py ...`) and keeps compatibility with existing wrappers.
- Expanded inventory ignore set in `tools/tools_inventory.py` with `build` and `dist`.
- Added maintainer docs note: `dev/reports/README.md` and ensured cleanup directory exists with `dev/reports/cleanup/.gitkeep`.

## What was removed

- Tracked files removed: none.
- Untracked generated artifacts removed:
  - `hooks/__pycache__/__init__.cpython-310.pyc`
  - `hooks/__pycache__/hooklib.cpython-310.pyc`

## Tools inventory and legacy map artifacts

- Inventory (MD): `dev/reports/cleanup/tools-inventory.md`
- Inventory (JSON): `dev/reports/cleanup/tools-inventory.json`
- Legacy grep hits: `dev/reports/cleanup/grep_legacy_hits.txt`
- Candidate list: `dev/reports/cleanup/candidate_tools_no_consumers.json`

## Shim map (validated)

| Shim entrypoint | Target | Known consumers | Decision |
|---|---|---|---|
| `tools/context-pack.sh` | `skills/review/scripts/context-pack.sh` | `docs/legacy/commands/review.md`, `docs/legacy/commands/qa.md`, `docs/legacy/commands/implement.md` | Keep shim (compat archive/docs consumers) |
| `tools/review-pack.sh` | `skills/review/scripts/review-pack.sh` | `docs/legacy/commands/review.md`, `README.md`, `README.en.md` | Keep shim (compat/docs consumers) |
| `tools/review-report.sh` | `skills/review/scripts/review-report.sh` | `docs/legacy/commands/review.md` | Keep shim (compat/docs consumers) |
| `tools/reviewer-tests.sh` | `skills/review/scripts/reviewer-tests.sh` | `hooks/gate-tests.sh`, `docs/legacy/commands/review.md` | Keep shim (runtime hook consumer exists) |

## Candidate removals (report-only, no deletions in this pass)

| Tool | Inventory consumers | Repo refs (excl self) | Decision |
|---|---:|---:|---|
| `tools/dag-export.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/identifiers.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/md-patch.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/md-slice.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/output-contract.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/plan-review-gate.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/prd-review-gate.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/tests-log.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/tools-inventory.sh` | `0` | `0` | Keep for now (possible follow-up removal) |
| `tools/researcher-context.sh` | `0` | `1` | Keep (still referenced) |
| `tools/preflight-prepare.sh` | `0` | `3` | Keep (still referenced) |
| `tools/review-report.sh` | `0` | `3` | Keep (still referenced) |
| `tools/review-pack.sh` | `0` | `5` | Keep (still referenced) |
| `tools/doctor.sh` | `0` | `6` | Keep (still referenced) |
| `tools/prd-review.sh` | `0` | `7` | Keep (still referenced) |
| `tools/context-pack.sh` | `0` | `8` | Keep (still referenced) |
| `tools/index-sync.sh` | `0` | `8` | Keep (still referenced) |
| `tools/analyst-check.sh` | `0` | `9` | Keep (still referenced) |
| `tools/status.sh` | `0` | `10` | Keep (still referenced) |
| `tools/research-check.sh` | `0` | `12` | Keep (still referenced) |
| `tools/loop-pack.sh` | `0` | `14` | Keep (still referenced) |
| `tools/diff-boundary-check.sh` | `0` | `17` | Keep (still referenced) |
| `tools/tasklist-normalize.sh` | `0` | `20` | Keep (still referenced) |
| `tools/status-summary.sh` | `0` | `23` | Keep (still referenced) |
| `tools/stage-result.sh` | `0` | `24` | Keep (still referenced) |
| `tools/prd-check.sh` | `0` | `26` | Keep (still referenced) |
| `tools/tasklist-check.sh` | `0` | `27` | Keep (still referenced) |
| `tools/set-active-feature.sh` | `0` | `54` | Keep (still referenced) |
| `tools/set-active-stage.sh` | `0` | `59` | Keep (still referenced) |

Notes: candidates with zero refs (excluding self and generated cleanup artifacts) are:
- `tools/dag-export.sh`
- `tools/identifiers.sh`
- `tools/md-patch.sh`
- `tools/md-slice.sh`
- `tools/output-contract.sh`
- `tools/plan-review-gate.sh`
- `tools/prd-review-gate.sh`
- `tools/tests-log.sh`
- `tools/tools-inventory.sh`

## Language policy drift (report-only)

- Policy SoT (`docs/skill-language.md`) says `skills/aidd-core/**`, `skills/aidd-loop/**`, and `skills/<stage>/**` are EN-only.
- Current stage skills use frontmatter `lang: ru` while content is English (no Cyrillic detected).
- Decision in this cleanup: no mass language/frontmatter changes; track as separate wave/PR to align policy and metadata.

## Commands executed (transcript summary)

```bash
# PHASE 0 baseline
tests/repo_tools/ci-lint.sh
tests/repo_tools/smoke-workflow.sh
python3 -m pytest

# PHASE 1 inventory + legacy scan
python3 tools/tools_inventory.py --help || python3 tools/tools-inventory.py --help
python3 tools/tools-inventory.py --repo-root . --output-json dev/reports/cleanup/tools-inventory.json --output-md dev/reports/cleanup/tools-inventory.md
rg -n "DEPRECATED:|Compatibility shim|legacy|shim|compat" tools hooks dev skills docs > dev/reports/cleanup/grep_legacy_hits.txt
git ls-files | rg -n "__pycache__|\.pyc$" || true
git ls-files | rg -n "\.pytest_cache|\.mypy_cache|\.ruff_cache|\.DS_Store" || true

# PHASE 2 cleanup changes
rm -rf hooks/__pycache__
python3 tools/tools_inventory.py --repo-root . --output-json dev/reports/cleanup/tools-inventory.json --output-md dev/reports/cleanup/tools-inventory.md

# PHASE 4 post-cleanup validation
tests/repo_tools/ci-lint.sh
tests/repo_tools/smoke-workflow.sh
python3 -m pytest
```

Validation summary: baseline and post-cleanup runs are all green (see log dirs above).
