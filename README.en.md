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
/feature-dev-aidd:tasks-new TICKET-123
/feature-dev-aidd:implement TICKET-123
/feature-dev-aidd:review TICKET-123
/feature-dev-aidd:qa TICKET-123
```

Optional for loop mode:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket TICKET-123`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket TICKET-123 --max-iterations 5`

## Update
```text
/plugin update feature-dev-aidd@aidd-local
```
Restart the Claude Code session after update.

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
