# TST-001 Audit Hardening Runbook

## Scope
- Incident class hardening for `06/07/08` audit fallout.
- Runtime safety for plugin-root discovery and launcher log I/O failures.
- Audit replay classification for deterministic RCA decisions.

## Preflight Checklist
1. Verify plugin root exists and has `/.claude-plugin` and `/skills`.
2. Verify run cwd is project workspace root.
3. Verify free disk bytes are above `AIDD_AUDIT_MIN_FREE_BYTES` (default `1073741824`).
4. Snapshot runner env:
   - `CLAUDE_PLUGIN_ROOT`
   - `AIDD_PLUGIN_DIR`
   - `PYTHONPATH`

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
4. `CONTRACT_MISMATCH`
   - `stage_result_missing_or_invalid` + `invalid-schema`.
5. `FLOW_BUG`
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

## Rerun Readiness Definition
1. Runtime: direct Python loop entrypoints resolve plugin root without manual env export.
2. Launcher: log write failures emit deterministic reason markers (`launcher_io_enospc`).
3. Audit replay tests pass for all TST-001 fixtures.
4. Prompt contract tests enforce:
   - disk preflight invariant
   - step-7 env wiring (`CLAUDE_PLUGIN_ROOT` + `PYTHONPATH`)
