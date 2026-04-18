# TST-001 Audit Hardening Runbook

> INTERNAL/DEV-ONLY: maintainer runbook for audit incident hardening and replay diagnostics.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

_Local evidence note: references like `aidd/reports/**` point to workspace-local artifacts and are not part of this git repository._

## Scope
- Hardening audit fallout for steps `06/07/08`
- Deterministic replay classification
- Runtime bootstrap and launcher I/O safety
- Single-scope seed guard (`I1` must not cascade to `I2`)

## Preflight
1. Verify plugin root contains `.claude-plugin/` and `skills/`.
2. Verify `PROJECT_DIR != PLUGIN_DIR`:
   ```bash
   [ "$(cd "$PROJECT_DIR" && pwd -P)" != "$(cd "$PLUGIN_DIR" && pwd -P)" ] || {
     echo "ENV_MISCONFIG(cwd_wrong): PROJECT_DIR must differ from PLUGIN_DIR"
     exit 12
   }
   ```
3. Verify free disk bytes >= `AIDD_AUDIT_MIN_FREE_BYTES` (`1073741824` default).
4. Snapshot `CLAUDE_PLUGIN_ROOT`, `AIDD_PLUGIN_DIR`, `PYTHONPATH`.
5. Bootstrap probes must use isolated Python mode: `python3 -S ... --help`.

## Classification Order
1. `ENV_BLOCKER`
   - plugin/slash command init evidence missing
   - `Unknown skill: feature-dev-aidd:*`
2. `ENV_MISCONFIG`
   - `cwd_wrong`
   - `no_space_left_on_device`
   - missing plugin env
   - `exit_code=143` without watchdog attribution
3. `PROMPT_EXEC_ISSUE`
   - watchdog kill (`exit_code=143`, `killed_flag=1`, `watchdog_marker=1`)
   - `seed_scope_cascade_detected`
   - `tests_env_dependency_missing`
   - launcher tokenization / command-not-found / repeated deterministic failure without new evidence
4. `CONTRACT_MISMATCH`
   - `stage_result_missing_or_invalid` + `invalid-schema`
5. `PROMPT_EXEC_ISSUE(scope_drift_recoverable)`
   - `stage_result_missing_or_invalid` + `scope_fallback_stale_ignored|scope_shape_invalid`
6. `FLOW_BUG`
   - only after the higher-priority classes are excluded

## Soft-Default Policy
- Default replay profile: `classification_profile=soft_default`
- Strict shadow remains available: `classification_profile=strict`
- Soft mode may downgrade terminal implement blockers to `WARN` to keep downstream signal, but must preserve `strict_shadow_classification`, `primary_root_cause`, and softening metadata.
- Global env/preflight blockers are never softened.

## Replay Workflow
1. Run classifier:
   ```bash
   python3 tests/repo_tools/aidd_audit_runner.py classify \
     --summary <step_summary.txt> \
     --log <step_log> \
     --termination <step_termination.txt> \
     --classification-profile soft_default \
     --aux-log <optional_loop_log> \
     --project-dir <project_dir> \
     --plugin-dir <plugin_dir>
   ```
2. Validate expected RCA on the canonical TST-001 fixtures.

## Canonical Launcher Rules
- Use only `python3 tests/repo_tools/aidd_stage_launcher.py ...`.
- Watchdog attribution must write sibling `*_termination_attribution.txt`.
- Valid stream-path sources are limited to `system/init` JSON, loop stream header lines, and fallback scan of `aidd/reports/loops/<ticket>/`.
- Never treat `tool_result` text or pasted artifact excerpts as valid stream-path sources.

## Rerun Ready Means
- Direct Python loop entrypoints self-bootstrap without manual env export
- Launcher emits deterministic log I/O reason markers
- Replay tests for TST-001 fixtures pass
- Prompt contracts still enforce disk preflight, step-7 env wiring, and single-scope seed guard

## Related Docs
- `docs/runbooks/w120-w121-w136-closure.md`
- `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`
