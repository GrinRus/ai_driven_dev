# Repository Cleanup Manual Checks

> INTERNAL/DEV-ONLY: manual-check register for cleanup candidates that require owner confirmation.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

## Policy

- Default action for unresolved API-tail candidates: `keep`.
- Promote to deletion only after two independent signals of non-usage and owner sign-off.

## API-tail candidates (Wave 4)

| Symbol | Path | Evidence snapshot | Current decision | Next validation step |
| --- | --- | --- | --- | --- |
| `get_report_paths` | `skills/aidd-core/runtime/reports/loader.py` | No internal call-sites via `rg`, public helper surface | `keep` | Keep as compat surface; only consider deprecate/remove after owner sign-off |
| `read_active_last_review_report_id` | `skills/aidd-core/runtime/runtime.py` | No internal call-sites via `rg`, exported helper | `keep` | Keep as compat surface; only consider deprecate/remove after owner sign-off |
| `normalize_stage_list` | `aidd_runtime/stage_lexicon.py` | No internal call-sites via `rg`, shared utility module | `keep` | Keep as compat surface; only consider deprecate/remove after owner sign-off |
| `detect_build_tools` | `skills/aidd-core/runtime/test_settings_defaults.py` | Internal constants used, function call-sites absent | `keep` | Keep as compat surface; verify downstream usage before any deprecate/remove decision |
| `test_settings_payload` | `skills/aidd-core/runtime/test_settings_defaults.py` | Internal constants used, function call-sites absent | `keep` | Keep as compat surface; verify downstream usage before any deprecate/remove decision |

## Resolution checklist

1. Record owner decision (`keep`, `deprecate`, `remove`) for each symbol.
2. For `remove`, add targeted regression tests for the affected contract.
3. Re-run `tests/repo_tools/ci-lint.sh` and full `python3 -m pytest -q tests` before merge.
