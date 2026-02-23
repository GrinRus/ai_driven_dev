# Loop Safety Policy

Use this policy in loop stages (`implement`, `review`, `qa`):

- Canonical loop execution always uses stage-chain orchestration.
- Manual stage-result writes and direct preflight invocation are forbidden operator paths.

Mandatory artifacts for successful loop step:
- `stage.preflight.result.json`
- `readmap` and `writemap`
- `actions.json` and apply log
- stage-chain runtime logs under `aidd/reports/logs/<stage>/<ticket>/<scope_key>/`

If mandatory artifacts are missing, fail as contract violation.
