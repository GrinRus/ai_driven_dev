# Loop Safety Policy

Use this policy in loop stages (`implement`, `review`, `qa`):

- `AIDD_SKIP_STAGE_WRAPPERS=1` is a diagnostics-only switch.
- In `strict` mode or stages `review|qa`:
  - return blocked with `reason_code=wrappers_skipped_unsafe`.
- In `fast` mode on `implement`:
  - warning `reason_code=wrappers_skipped_warn` is allowed only for diagnostics.

Mandatory artifacts for successful loop step:
- `stage.preflight.result.json`
- `readmap` and `writemap`
- `actions.json` and apply log
- stage wrapper/runtime logs under `aidd/reports/logs/<stage>/<ticket>/<scope_key>/`

If mandatory artifacts are missing, fail as contract violation.
