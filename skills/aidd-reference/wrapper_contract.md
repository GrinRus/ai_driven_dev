# Wrapper Contract (W92)

This document defines the stable wrapper interface for stage-local scripts.

## Interface (required)

Wrappers **MUST** accept the following arguments:

- `--ticket`
- `--scope-key`
- `--work-item-key`
- `--stage`
- `--actions <path>`

If `--actions` is omitted, the wrapper **MUST** compute the canonical actions path
and print to stdout:

```
actions_path=aidd/reports/actions/<ticket>/<scope_key>/<stage>.actions.json
```

## Canonical paths

- Actions template:
  `aidd/reports/actions/<ticket>/<scope_key>/<stage>.actions.template.json`
- Actions actual:
  `aidd/reports/actions/<ticket>/<scope_key>/<stage>.actions.json`
- Apply log:
  `aidd/reports/actions/<ticket>/<scope_key>/<stage>.apply.jsonl` (or `.log` if explicitly configured)

## Logging & output limits

- Wrapper logs go to:
  `aidd/reports/logs/<stage>/<ticket>/<scope_key>/wrapper.<name>.<timestamp>.log`
- Stdout limit: **<= 200 lines OR <= 50KB**
- Stderr limit: **<= 50 lines** (summary/errors only)
- Any large output must be written to `aidd/reports/**` and referenced by path.

## Exit codes

- `0` on success
- non-zero on failure (validation errors, DocOps errors, missing inputs)

## Workspace-only writes

- Artifacts and logs **MUST** be written to the workspace under `aidd/reports/**`.
- Never write artifacts or logs to `${CLAUDE_PLUGIN_ROOT}`.

## Assets

- Assets are read-only and must be referenced via `${CLAUDE_PLUGIN_ROOT}`.
- Do not use `../` to escape plugin root.

## DocOps-only updates (loop stages)

- Loop stages (implement/review/qa/status) **must not** directly edit:
  - `aidd/docs/tasklist/**`
  - `aidd/reports/context/**`
- All updates go through **Actions + DocOps apply**.
