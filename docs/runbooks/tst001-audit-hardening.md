# TST-001 Audit Hardening Runbook

> INTERNAL/DEV-ONLY: maintainer runbook for audit incident hardening and replay diagnostics.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: historical

## Scope
- Incident class hardening for `06/07/08` audit fallout.
- Runtime safety for plugin-root discovery and launcher log I/O failures.
- Audit replay classification for deterministic RCA decisions.

## Preflight Checklist
1. Verify plugin root exists and has `/.claude-plugin` and `/skills`.
2. Verify run cwd is project workspace root.
   - Shell-safe invariant check:
     ```bash
     [ "$(cd "$PROJECT_DIR" && pwd -P)" != "$(cd "$PLUGIN_DIR" && pwd -P)" ] || {
       echo "ENV_MISCONFIG(cwd_wrong): PROJECT_DIR must differ from PLUGIN_DIR"
       exit 12
     }
     ```
3. Verify free disk bytes are above `AIDD_AUDIT_MIN_FREE_BYTES` (default `1073741824`).
4. Snapshot runner env:
   - `CLAUDE_PLUGIN_ROOT`
   - `AIDD_PLUGIN_DIR`
   - `PYTHONPATH`
5. Runtime bootstrap probe must use isolated Python mode (`python3 -S ... --help`) so site-packages cannot mask missing `aidd_runtime` bootstrap wiring.

If disk is below threshold, stop with `ENV_MISCONFIG(no_space_left_on_device)`.

## Classification Decision Tree
1. `ENV_BLOCKER`
   - `Unknown skill: feature-dev-aidd:*`
   - plugin/slash command init evidence missing for slash-based runs.
2. `ENV_MISCONFIG`
   - `no_space_left_on_device` from preflight or launcher error.
   - `CLAUDE_PLUGIN_ROOT (or AIDD_PLUGIN_DIR) is required`.
   - `exit_code=143` with `killed_flag=0` or missing watchdog marker.
3. `PROMPT_EXEC_ISSUE`
   - `exit_code=143` with `killed_flag=1` and `watchdog_marker=1`.
   - launcher tokenization/command-not-found (`127`).
   - repeated deterministic command failure without new evidence (`reason_code=repeated_command_failure_no_new_evidence`).
4. `CONTRACT_MISMATCH`
   - `stage_result_missing_or_invalid` + `invalid-schema`.
5. `PROMPT_EXEC_ISSUE(scope_drift_recoverable)`
   - `stage_result_missing_or_invalid` + diagnostics marker `scope_fallback_stale_ignored|scope_shape_invalid`.
6. `FLOW_BUG`
   - only after all higher-priority classes are not matched.

## `result_count=0` Policy
- `result_count=0` is telemetry-only until top-level payload is checked.
- Detect top-level status from run log (`status=...` or JSON status payload).
- Only classify `no_top_level_result` if top-level status is absent.

## Replay Workflow
1. Run classifier:
```bash
python3 tests/repo_tools/aidd_audit_runner.py classify \
  --summary <step_summary.txt> \
  --log <step_log> \
  --termination <step_termination.txt> \
  --aux-log <optional_loop_log> \
  --project-dir <project_dir> \
  --plugin-dir <plugin_dir>
```
1. Validate expected outputs:
   - `06_implement -> ENV_MISCONFIG(no_space_left_on_device)`
   - `06_review -> NOT_VERIFIED(killed)+PROMPT_EXEC_ISSUE(watchdog_terminated)`
   - `07_loop_run#1 -> ENV_MISCONFIG(loop_runner_env_missing)`
   - `07_loop_run#2 -> BLOCKED(recoverable ralph path observed)`
   - `08_qa -> NOT_VERIFIED(killed)+PROMPT_EXEC_ISSUE(watchdog_terminated)`

## Canonical Launcher & Stream Sources
1. Canonical launcher path:
   ```bash
   python3 tests/repo_tools/aidd_stage_launcher.py \
     --project-dir <project_dir> \
     --plugin-dir <plugin_dir> \
     --audit-dir <audit_dir> \
     --step <step_key> \
     --run <n> \
     --ticket <ticket> \
     --stage-command "<slash command>"
   ```
2. Stream path extraction hierarchy:
   - `source=init_json`: only from `type=system, subtype=init` JSON payload.
   - `source=loop_stream_header`: only from control lines `==> streaming enabled ... stream=... log=...`.
   - `source=fallback_scan`: only from `aidd/reports/loops/<ticket>/`.
3. Prohibited extraction:
   - `tool_result` content, artifact excerpts, and generic prose lines are never valid stream-path sources.
4. Fallback freshness window:
   - Include fallback stream files only when `mtime >= run_start_epoch - 5s`.
   - Older files are treated as stale and excluded from liveness set.

## Rerun Readiness Definition
1. Runtime: direct Python loop entrypoints resolve plugin root without manual env export.
2. Launcher: log write failures emit deterministic reason markers (`launcher_io_enospc`).
3. Audit replay tests pass for all TST-001 fixtures.
4. Prompt contract tests enforce:
   - disk preflight invariant
   - step-7 env wiring (`CLAUDE_PLUGIN_ROOT` + `PYTHONPATH`)

## Related Closure Evidence
- Wave stabilization closure summary: `docs/runbooks/w120-w121-w136-closure.md`.
- Baseline report: `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`.
