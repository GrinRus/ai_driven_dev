# Prod-like Hardening Final Report

Generated at: `2026-02-25T09:27:08Z`
Branch: `codex/prod-like-hardening`

## Summary
- Status: `DONE`
- Scope: aggressive cleanup + deep script restructuring + docs parity + dist profile.
- Migration mode: breaking changes accepted.

## Implemented Waves

### Wave 0
- Created isolated worktree and implementation branch.

### Wave 1
- Moved prompt scripts from repo root to `dev/prompts/ralph/`.
- Updated all references in tests/backlog/topology audit.
- Removed tracked generated revision artifacts under `dev/reports/revision/*`.
- Switched topology-audit default outputs to `aidd/.cache/revision/*`.
- Added `tests/repo_tools/repo_hygiene.py` and integrated it into CI lint pipeline.

### Wave 2
- Migrated hook entrypoints from `.sh` naming to `.py` naming.
- Updated hook wiring in `hooks/hooks.json` and all call sites/tests/docs/CI paths.
- Removed `tests/repo_tools/python-shebang-allowlist.txt` and replaced policy with strict hook `.py` checks.

### Wave 3
- Split `format_and_test` into thin facade + implementation part (`hooks/format_and_test_parts/core.py`).
- Modularized repo tool entrypoints:
  - `tests/repo_tools/ci-lint.sh` -> facade to `tests/repo_tools/ci/main.sh`
  - `tests/repo_tools/smoke-workflow.sh` -> facade to `tests/repo_tools/smoke/main.sh`

### Wave 4
- Applied thin-facade split for oversized runtime modules to `*_parts/core.py`.
- Tightened runtime module guard thresholds to `warn=450`, `error=700`.
- Result: runtime modules over warn threshold = `0`.

### Wave 5
- Added docs parity guard: `tests/repo_tools/docs_parity_guard.py`.
- Added migration runbook: `docs/runbooks/prod-like-breaking-migration.md`.
- Updated RU/EN docs and AGENTS required-check matrix.

### Wave 6
- Added dist manifest: `.claude-plugin/dist-manifest.json`.
- Added dist validation: `tests/repo_tools/dist_manifest_check.py`.
- Added CI job `dist-check` in `.github/workflows/ci.yml`.

### Wave 7
- Bumped plugin version metadata to `0.3.0` (`plugin.json`, `marketplace.json`).
- Completed full regression and smoke validation.

## Validation Results
- `tests/repo_tools/ci-lint.sh` -> PASS
- `tests/repo_tools/smoke-workflow.sh` -> PASS
- `python3 tests/repo_tools/repo_hygiene.py` -> PASS
- `python3 tests/repo_tools/docs_parity_guard.py --root .` -> PASS
- `python3 tests/repo_tools/dist_manifest_check.py --root .` -> PASS

## Metrics
- Runtime entrypoints (`skills/**/runtime/*.py`): `88`
- Runtime entrypoints over 450 lines: `0`
- Git changed paths in this migration: `98`

## Notes
- Breaking path migration is documented in `docs/runbooks/prod-like-breaking-migration.md`.
- Generated topology revision outputs are no longer tracked and should remain cache-only.
