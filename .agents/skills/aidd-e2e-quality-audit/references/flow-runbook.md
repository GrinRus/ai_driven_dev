# Flow Runbook

## Purpose
- Keep the Codex-native audit layer thin.
- Reuse the existing repo tools instead of embedding a new mega prompt or duplicating runtime logic.

## Preflight
1. Run `python3 tests/repo_tools/build_e2e_prompts.py --check`.
2. Resolve workspace vs plugin paths:
   - `--project-dir` points at the workspace root or direct `aidd` root.
   - `--plugin-dir` points at the repository root that contains `.claude-plugin/` and `skills/`.
3. Fail fast if the launcher reports:
   - `cwd_wrong`
   - `plugin_not_loaded`
   - `no_space_left_on_device`

## Stage order
- `00_status`
- `01_idea_new`
- `02_research`
- `03_plan_new`
- `04_review_spec`
- `05_tasks_new`
- `06_implement` (`full` profile only)
- `07_review` (`full` profile only)
- `08_qa` (`full` profile only)

`smoke` stops after `05_tasks_new`.

## Launcher contract
- Use `tests/repo_tools/aidd_stage_launcher.py`.
- One stage at a time, one run index at a time.
- The launcher remains the owner of raw stage captures, including:
  - `*_run1.summary.txt`
  - `*_run1.init_check.txt`
  - `*_run1.disk_preflight.txt`
  - stage stdout/stderr captures

## Post-run analysis
1. Run `tests/repo_tools/aidd_audit_runner.py rollup`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/artifact_audit.py`.
3. Write one deterministic pack under:
   `aidd/reports/events/codex-e2e-audit/run-<timestamp>/`

## Non-goals
- No replacement of stage runtime with Codex-native prompts.
- No parallel stage execution.
- No auto-fix pass in `v1`.
