# Loop Stage Skill Contract

Shared contract for `skills/implement/SKILL.md`, `skills/review/SKILL.md`, and `skills/qa/SKILL.md`.

## Canon
- Execute only via the canonical stage-chain.
- Internal preflight and postflight remain orchestration details, not operator commands.
- Read order after preflight artifacts: `readmap.md -> loop pack -> review.latest.pack.md -> rolling context pack`.
- If stdout/stderr contains `can't open file .../skills/.../runtime/...`, stop with `BLOCKED runtime_path_missing_or_drift`.
- `actions_apply.py` postflight and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py` stay canonical.
- Non-canonical stage-result paths under `skills/aidd-loop/runtime/` are forbidden.
