# AGENTS

Single workspace entrypoint for AIDD operators. Repository maintainer rules live in plugin-root `AGENTS.md`.

## Skill-first Canon
- Runtime topology: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/SKILL.md`.
- Shared policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-policy/SKILL.md`.
- Loop policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/SKILL.md`.
- Stage lexicon: `aidd/docs/shared/stage-lexicon.md`.

## Baseline Rules
- All workspace artifacts live under `aidd/**` relative to the project root.
- For output format, question format, read discipline, and runtime-path safety, follow `skills/aidd-policy`.
- For shared runtime ownership and entrypoint discovery, follow `skills/aidd-core`.
- `AIDD:READ_LOG` is required for artifact reads and for any fallback full-read reason.
- Stage/shared runtime entrypoints use the Python-only canon: `skills/*/runtime/*.py`.
- Shell wrappers are allowed only for hooks and platform glue; stage orchestration must not depend on `skills/*/scripts/*`.
- Wrapper output must stay within the output budget: stdout <= 200 lines or <= 50KB, stderr <= 50 lines; send large outputs to `aidd/reports/**`.
- Stage-chain orchestration (`preflight -> run -> postflight -> stage_result`) is mandatory for loop stages.

## Evidence read policy
- Primary research evidence: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice on demand with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>"`.
- Legacy pre-RLM research context/targets artifacts do not count as gate evidence.

## User Answers
Keep answers within the same command run without switching stages. If answers arrive in chat, request:

```md
## AIDD:ANSWERS
AIDD:ANSWERS Q1=A; Q2="short text with spaces"
```
