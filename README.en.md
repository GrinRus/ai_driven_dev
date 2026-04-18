# AIDD Claude Code Plugin

> Minimal artifact-driven workflow for Claude Code: idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa.

## Canonical Guide
The canonical user guide is [`README.md`](README.md). This file is a compact English mirror for install, startup, and loop entrypoints.

## Install
```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

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

Loop mode entrypoints:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket TICKET-123`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket TICKET-123 --max-iterations 5`

## Minimal Troubleshooting
- Missing slash commands after update: rerun `/plugin update feature-dev-aidd@aidd-local` and restart Claude Code.
- `ModuleNotFoundError: No module named 'aidd_runtime'`: reinstall the plugin and restart the session.
- Workspace not initialized: run `/feature-dev-aidd:aidd-init`, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`.

## Documentation
### Public docs
- `README.md` — canonical user guide.
- `README.en.md` — compact English mirror.
- `CHANGELOG.md` — user-facing release notes.
- `SECURITY.md` and `SUPPORT.md` — security disclosure and support policy.
- `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` — contribution and behavior rules.
