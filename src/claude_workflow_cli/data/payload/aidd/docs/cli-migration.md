# CLI Migration Map

Таблица отражает перенос кастомной логики из payload в `claude-workflow`.

| Legacy path (payload) | New CLI command | Consumers |
| --- | --- | --- |
| `aidd/tools/set_active_feature.py` | `claude-workflow set-active-feature` | `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`, `/qa`, `/researcher`, агенты `analyst/planner/implementer/reviewer/qa/researcher/plan-reviewer/prd-reviewer/validator` |
| `aidd/tools/set_active_stage.py` | `claude-workflow set-active-stage` | `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`, `/qa`, `/review-spec`, `/researcher`, агенты `analyst/planner/implementer/reviewer/qa/researcher/plan-reviewer/prd-reviewer/validator` |
| `aidd/scripts/prd-review-agent.py` | `claude-workflow prd-review` | `/review-spec` (`prd-reviewer`) |
| `aidd/scripts/plan_review_gate.py` | `claude-workflow plan-review-gate` | `aidd/hooks/gate-workflow.sh` |
| `aidd/scripts/prd_review_gate.py` | `claude-workflow prd-review-gate` | `aidd/hooks/gate-workflow.sh`, `aidd/hooks/gate-prd-review.sh` |
| `aidd/scripts/qa-agent.py` | `claude-workflow qa` | `aidd/hooks/gate-qa.sh` |
| `aidd/tools/researcher_context.py` | `claude-workflow researcher-context` | CLI usage + `set-active-feature` targets refresh |
| `aidd/scripts/context_gc/*` | `claude-workflow context-gc <precompact, sessionstart, pretooluse, stop, userprompt>` | `aidd/hooks/hooks.json` |
| `aidd/tools/run_cli.py` | removed | прямые вызовы `claude-workflow` в хуках |
| `aidd/scripts/smoke-workflow.sh` | `claude-workflow smoke` | CLI smoke runner |
