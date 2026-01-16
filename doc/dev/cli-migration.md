# Runtime Wrapper Map

Таблица отражает перенос кастомной логики из legacy payload в python-обёртки и пакет `aidd_runtime`.

| Legacy path (payload) | New wrapper | Consumers |
| --- | --- | --- |
| `aidd/tools/set_active_feature.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-feature` | `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`, `/qa`, `/researcher` + агенты `analyst/planner/implementer/reviewer/qa/researcher/plan-reviewer/prd-reviewer/validator` |
| `aidd/tools/set_active_stage.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage` | `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`, `/qa`, `/review-spec`, `/researcher` + агенты `analyst/planner/implementer/reviewer/qa/researcher/plan-reviewer/prd-reviewer/validator` |
| `aidd/scripts/prd-review-agent.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli prd-review` | `/review-spec` (`prd-reviewer`) |
| `aidd/scripts/plan_review_gate.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli plan-review-gate` | `hooks/gate-workflow.sh` |
| `aidd/scripts/prd_review_gate.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli prd-review-gate` | `hooks/gate-workflow.sh`, `hooks/gate-prd-review.sh` |
| `aidd/scripts/qa-agent.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa` | `hooks/gate-qa.sh` |
| `aidd/tools/researcher_context.py` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research --targets-only` | `set-active-feature` targets refresh |
| `aidd/scripts/context_gc/*` | `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli context-gc <precompact, sessionstart, pretooluse, stop, userprompt>` | `hooks/hooks.json` |
| `aidd/tools/run_cli.py` | removed | прямые вызовы CLI в хуках заменены на python-обёртки |
| `scripts/smoke-workflow.sh` | `repo_tools/smoke-workflow.sh` | e2e smoke runner (repo-only) |
