Задача: **AIDD E2E Flow Audit (TST-001)**.

Роль: один аудитор-агент. Проведи flow по canonical AIDD path, не исправляй проект и не делай ручные правки `aidd/docs/**` или `aidd/reports/**` ради прохождения.

## 1) Must read

{{MUST_READ_MANIFEST}}

## 2) Environment

- `PROJECT_DIR=<absolute-path-to-target-workspace>`
- `PLUGIN_DIR=<absolute-path-to-plugin-repo>`
- `CLAUDE_PLUGIN_ROOT=$PLUGIN_DIR`
- `TICKET=TST-001`
- `STAGE_OUTPUT_MODE=stream-json|text` (default: `stream-json`)
- `BLOCKED_POLICY=strict|ralph` (default: `ralph`)
- `SEVERITY_PROFILE=conservative`
- Pre-run invariant: `PROJECT_DIR must differ from PLUGIN_DIR`

## 3) Core rules

{{INCLUDE:includes/shared_rules_core.md}}

## 4) Canonical execution

- Use only canonical Python runtime paths under `$PLUGIN_DIR/skills/*/runtime/*.py`.
- Use canonical launcher `python3 $PLUGIN_DIR/tests/repo_tools/aidd_stage_launcher.py ...`.
- Run stage commands only from `PROJECT_DIR`.
- Do not use shell wrappers, direct internal preflight entrypoints, or manual writes to `stage.*.result.json`.
- Readiness gate lives in `AUDIT_DIR/05_precondition_block.txt`.

## 5) Common incident policy

- If canonical runtime fails with `ModuleNotFoundError: No module named 'aidd_runtime'`, classify as `flow bug (runtime_bootstrap_missing)`, not `ENV_BLOCKER`.
- If log shows `can't open file .../skills/.../runtime/...`, classify as `prompt-flow drift (non-canonical runtime path)`.
- Use `policy matrix v2` only for recoverable blocked handling, not for env blockers.
- Keep `result_count=0` as telemetry until top-level payload is checked.

## 6) Step outline

1. Step `0`: clean state, capture `git status`, create `AUDIT_DIR`.
2. Step `1`: plugin/load/env preflight, init health, disk check, launcher check.
3. Step `2`: workspace bootstrap and status baseline.
4. Step `3`: `idea-new`.
5. Step `4`: `researcher`.
6. Step `5`: `plan-new`, `review-spec`, readiness gate refresh into `05_precondition_block.txt`.
7. Downstream stages must honor canonical handoffs and evidence-first classification.
