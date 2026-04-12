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
| `get_report_paths` | `skills/aidd-core/runtime/reports/loader.py` | No internal call-sites via `rg`, public helper surface | `manual_check` | Confirm external consumers (if any), then deprecate/remove |
| `read_active_last_review_report_id` | `skills/aidd-core/runtime/runtime.py` | No internal call-sites via `rg`, exported helper | `manual_check` | Confirm external consumers, then deprecate/remove |
| `normalize_stage_list` | `aidd_runtime/stage_lexicon.py` | No internal call-sites via `rg`, shared utility module | `manual_check` | Confirm extension/plugin consumers, then deprecate/remove |
| `detect_build_tools` | `skills/aidd-core/runtime/test_settings_defaults.py` | Internal constants used, function call-sites absent | `manual_check` | Verify downstream hook usage expectations |
| `test_settings_payload` | `skills/aidd-core/runtime/test_settings_defaults.py` | Internal constants used, function call-sites absent | `manual_check` | Verify downstream hook usage expectations |

## Resolution checklist

1. Record owner decision (`keep`, `deprecate`, `remove`) for each symbol.
2. For `remove`, add targeted regression tests for the affected contract.
3. Re-run `tests/repo_tools/ci-lint.sh` and full `python3 -m pytest -q tests` before merge.
