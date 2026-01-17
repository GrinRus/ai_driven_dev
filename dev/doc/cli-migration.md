# Runtime Wrapper Map

Таблица отражает перенос кастомной логики из legacy payload в python-entrypoint скрипты (`tools/` и `hooks/`).

| Legacy path (payload) | New entrypoint | Consumers |
| --- | --- | --- |
| `aidd/tools/set_active_feature.py` | `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh` | `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:plan-new`, `/feature-dev-aidd:tasks-new`, `/feature-dev-aidd:implement`, `/feature-dev-aidd:review`, `/feature-dev-aidd:qa`, `/feature-dev-aidd:researcher` + агенты `analyst/planner/implementer/reviewer/qa/researcher/plan-reviewer/prd-reviewer/validator` |
| `aidd/tools/set_active_stage.py` | `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh` | `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:plan-new`, `/feature-dev-aidd:tasks-new`, `/feature-dev-aidd:implement`, `/feature-dev-aidd:review`, `/feature-dev-aidd:qa`, `/feature-dev-aidd:review-spec`, `/feature-dev-aidd:researcher` + агенты `analyst/planner/implementer/reviewer/qa/researcher/plan-reviewer/prd-reviewer/validator` |
| `aidd/scripts/prd-review-agent.py` | `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh` | `/feature-dev-aidd:review-spec` (`prd-reviewer`) |
| `aidd/scripts/plan_review_gate.py` | `${CLAUDE_PLUGIN_ROOT}/tools/plan-review-gate.sh` | `hooks/gate-workflow.sh` |
| `aidd/scripts/prd_review_gate.py` | `${CLAUDE_PLUGIN_ROOT}/tools/prd-review-gate.sh` | `hooks/gate-workflow.sh`, `hooks/gate-prd-review.sh` |
| `aidd/scripts/qa-agent.py` | `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh` | `hooks/gate-qa.sh` |
| `aidd/tools/researcher_context.py` | `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --targets-only` | `set-active-feature` targets refresh |
| `aidd/scripts/context_gc/*` | `${CLAUDE_PLUGIN_ROOT}/hooks/context-gc-{precompact,sessionstart,pretooluse,stop,userprompt}.sh` | `hooks/hooks.json` |
| `aidd/tools/run_cli.py` | removed | прямые вызовы CLI в хуках заменены на python-обёртки |
| `scripts/smoke-workflow.sh` | `dev/repo_tools/smoke-workflow.sh` | e2e smoke runner (repo-only) |
