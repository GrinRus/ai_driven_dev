# AIDD Claude Code Plugin

> Minimal AI-driven workflow template for Claude Code: idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa.

## What it is
AIDD adds a ready workflow, slash commands, and baseline quality checks to Claude Code using artifact-driven development (`prd`, `plan`, `tasklist`, `qa`).

## Requirements
- Claude Code with plugin marketplace commands enabled.
- Minimum tested version: Claude Code `1.0.0`.
- `python3`, `git`, `rg`.

## Install
```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

The self-hosted channel updates only through immutable tag refs `vX.Y.Z`.

## Quick Start
```text
/feature-dev-aidd:aidd-init
/feature-dev-aidd:idea-new TICKET-123 "Short feature note"
/feature-dev-aidd:researcher TICKET-123
/feature-dev-aidd:plan-new TICKET-123
/feature-dev-aidd:review-spec TICKET-123
/feature-dev-aidd:tasks-new TICKET-123
/feature-dev-aidd:implement TICKET-123
/feature-dev-aidd:review TICKET-123
/feature-dev-aidd:qa TICKET-123
```

## Commands
| Command | When to run |
| --- | --- |
| `/feature-dev-aidd:aidd-init` | Once per workspace or after removing `aidd/`. |
| `/feature-dev-aidd:idea-new <ticket> "<note>"` | Start a feature and create the initial PRD draft. |
| `/feature-dev-aidd:researcher <ticket>` | Gather research context before planning. |
| `/feature-dev-aidd:plan-new <ticket>` | Build the implementation plan. |
| `/feature-dev-aidd:review-spec <ticket>` | Validate plan/PRD alignment before tasklist. |
| `/feature-dev-aidd:tasks-new <ticket>` | Generate tasklist for implementation. |
| `/feature-dev-aidd:implement <ticket>` | Implement tasks from tasklist. |
| `/feature-dev-aidd:review <ticket>` | Review implementation and capture follow-ups. |
| `/feature-dev-aidd:qa <ticket>` | Run final QA gate. |
| `/feature-dev-aidd:status [ticket]` | Show quick status for the active or specified ticket. |

Optional for loop mode:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket TICKET-123`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket TICKET-123 --max-iterations 5`

## Update
```text
/plugin update feature-dev-aidd@aidd-local
```
Restart the Claude Code session after update.

## Troubleshooting
### New slash commands are missing after update
1. Run `/plugin update feature-dev-aidd@aidd-local`.
2. Restart the Claude Code session completely.

### Error `ModuleNotFoundError: No module named 'aidd_runtime'`
1. Run `/plugin remove feature-dev-aidd@aidd-local`.
2. Run `/plugin install feature-dev-aidd@aidd-local`.
3. Restart the Claude Code session.

### Commands report that workspace is not initialized
1. Run `/feature-dev-aidd:aidd-init`.
2. Check environment diagnostics:
   `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`

## Documentation
### Public docs
- `README.md` and `README.en.md` — install, run, update.
- `CHANGELOG.md` — user-facing release notes.
- `SECURITY.md` and `SUPPORT.md` — security disclosure and support policy.
- `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` — contribution and behavior rules.

## Contributing
Contribution process: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
