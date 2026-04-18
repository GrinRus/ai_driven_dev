Задача: **AIDD E2E Quality Audit (TST-002)**.

Роль: один quality-аудитор-агент. Сначала доведи standalone flow до terminal state по canonical AIDD path, затем выполни quality gate и backlog-aware write-safety.

## 1) Must read

{{MUST_READ_MANIFEST}}

- `$PLUGIN_DIR/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`
- `$PLUGIN_DIR/docs/backlog.md`
- `$PLUGIN_DIR/skills/review-spec/SKILL.md`

## 2) Environment

- `PROJECT_DIR=<absolute-path-to-target-workspace>`
- `PLUGIN_DIR=<absolute-path-to-plugin-repo>`
- `CLAUDE_PLUGIN_ROOT=$PLUGIN_DIR`
- `TICKET=TST-002`
- `BASE_PROMPT=$PLUGIN_DIR/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`
- `BACKLOG_PATH=$PLUGIN_DIR/docs/backlog.md`
- `QUALITY_FINAL_MARKER=QUALITY_AUDIT_COMPLETE`
- `QUALITY_GATE_POLICY=strict`
- `WAVE_WRITE_MODE=on-findings|always`
- Pre-run invariant: `PROJECT_DIR must differ from PLUGIN_DIR`

## 3) Core rules

{{INCLUDE:includes/shared_rules_core.md}}

## 4) Quality-specific rules

- Keep external flow behavior stable: slash commands, hook names, artifact names.
- Preserve inherited flow evidence around `runtime_bootstrap_missing` and `AUDIT_DIR/05_precondition_block.txt`.
- Do not modify target project just to improve the score.
- `docs/backlog.md` is the only allowed plugin write during the quality step.
- Create a new wave only for systemic AIDD findings; keep product-specific findings in the improvement plan.
- Use `Wave <NNN>` and `W<NNN>-1` markers when writing a backlog wave.

## 5) Step outline

1. Run the inherited flow steps.
2. Evaluate final feature state, code quality, artifact quality, and acceptance traceability.
3. Produce quality verdict and optional backlog wave.
4. End with the exact final marker:
`QUALITY_AUDIT_COMPLETE TST-002 status=<PASS|WARN|FAIL> wave=<WNNN|none> feature_final_state=<REACHED|NOT_REACHED>`
