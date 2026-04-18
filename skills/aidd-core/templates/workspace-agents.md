# AGENTS

Single entrypoint for AIDD runtime agents in a workspace. Repository maintainer guidance lives in the plugin-root `AGENTS.md`.

## Skill-first Canon
- Runtime topology: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/SKILL.md`.
- Shared policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-policy/SKILL.md`.
- Loop policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/SKILL.md`.
- This document is a user-facing overview; do not duplicate algorithms from the skills.
- Stage lexicon (public/internal): `aidd/docs/shared/stage-lexicon.md`.

## Baseline Rules
- All workspace artifacts live under `aidd/**` relative to the project root.
- For output format, question format, read discipline, and runtime-path safety, follow `skills/aidd-policy`.
- For runtime ownership and shared entrypoint discovery, follow `skills/aidd-core`.
- `AIDD:READ_LOG` is required for artifact reads and for any fallback full-read reason.
- Loop discipline lives in `skills/aidd-loop`.
- Stage/shared runtime entrypoints use the Python-only canon: `skills/*/runtime/*.py`.
- Shared entrypoints use canonical paths such as `skills/aidd-core/runtime/*.py`, `skills/aidd-loop/runtime/*.py`, and `skills/aidd-rlm/runtime/*.py`.
- Shell wrappers are allowed only for hooks and platform glue; stage orchestration must not depend on `skills/*/scripts/*`.
- `tools/` contains import stubs and repo-only tooling only.
- Wrapper output must stay within the output budget: stdout <= 200 lines or <= 50KB, stderr <= 50 lines; send large outputs to `aidd/reports/**`.
- Stage-chain orchestration (`preflight -> run -> postflight -> stage_result`) is mandatory for loop stages.

## Evidence read policy (summary)
- Primary research evidence: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice on demand: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>"`.

## Migration Policy (Legacy -> RLM-only)
- Legacy pre-RLM research context/targets artifacts are not read by gates and do not count as evidence.
- For older workspaces, rebuild the research stage with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto`.
- If `rlm_status=pending` after research, hand off to the shared owner with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`.
- Plan/review/qa readiness requires the minimum RLM set: `rlm-targets`, `rlm-manifest`, `rlm.worklist.pack`, `rlm.nodes`, `rlm.links`, and `rlm.pack`.

## User Answers
Keep answers within the same command run without switching stages. If answers arrive in chat, request this block:
```
## AIDD:ANSWERS
AIDD:ANSWERS Q1=A; Q2="short text with spaces"
```
