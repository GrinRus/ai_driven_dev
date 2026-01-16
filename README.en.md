# AIDD Claude Code Plugin - Language-agnostic Workflow Template

> A ready-to-use Claude Code plugin: slash commands, agents, hooks, and templates for the idea → research → plan → review-spec → tasklist → implement → review → qa flow.

## Table of Contents
- [What it is](#what-it-is)
- [Get Started](#get-started)
- [Scripts and Checks](#scripts-and-checks)
- [Slash Commands](#slash-commands)
- [Prerequisites](#prerequisites)
- [Path Troubleshooting](#path-troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Sync Guide
- Always edit `README.md` (RU) first, then update this translation in the same commit.
- Mirror section structure, headlines, and links.
- Update the date below whenever both files are aligned.

_Last sync with `README.md`: 2026-01-17._

## What it is
AIDD adds a ready-to-use development process with agents and gates. You get the `aidd/` structure, slash commands, and a consistent way to manage PRDs, plans, and tasklists.

Key features:
- Slash commands and agents for the idea → research → plan → review-spec → tasklist → implement → review → qa flow.
- Research is required before planning: `research-check` expects status `reviewed`.
- PRD/Plan Review/QA gates and safe hooks (stage-aware).
- Auto-formatting and selective tests during the `implement` stage.
- Unified `AIDD:ANSWERS` format plus Q identifiers in `AIDD:OPEN_QUESTIONS` (the plan references `PRD QN` without duplication).
- Branch and commit conventions via `aidd/config/conventions.json`.

## Get Started

### 1. Add the marketplace and install the plugin

```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

### 2. Initialize the workspace

```text
/aidd-init
```

For CI or manual use:

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli init
```

### 3. Run a feature in Claude Code

```text
/idea-new STORE-123 checkout-discounts
/researcher STORE-123
/plan-new STORE-123
/review-spec STORE-123
/tasks-new STORE-123
/implement STORE-123
/review STORE-123
/qa STORE-123
```

Notes:
- `/idea-new` takes a `ticket` and an optional `slug-hint`.
- After `/idea-new`, answer the analyst questions and update the PRD to `Status: READY` (check with `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli analyst-check --ticket STORE-123`).
- Capture answers in `AIDD:ANSWERS` (`Answer N` format) and keep `AIDD:OPEN_QUESTIONS` synced as `Q1/Q2/...` — when the `AIDD:OPEN_QUESTIONS` section is present, `analyst-check` blocks mismatches.
- In the plan, reference questions as `PRD QN` instead of duplicating the text.
- `/review-spec` performs plan review and PRD review in one step.

## Scripts and Checks

| Command | Description |
| --- | --- |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli init` | Create `./aidd` from templates (no overwrite) |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research --ticket <ticket>` | Generate research context |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research-check --ticket <ticket>` | Verify Research status `reviewed` |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli analyst-check --ticket <ticket>` | Verify PRD `READY` and Q/A sync |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress --source <stage> --ticket <ticket>` | Confirm tasklist progress |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Run QA report + gate |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasklist-check --ticket <ticket>` | Validate tasklist contract |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasks-derive --source <qa\|research\|review> --append --ticket <ticket>` | Append handoff tasks |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli status --ticket <ticket> [--refresh]` | Ticket status summary (stage/artifacts/events) |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli index-sync --ticket <ticket>` | Refresh ticket index `aidd/docs/index/<ticket>.yaml` |
| `repo_tools/ci-lint.sh` | CI linters + unit tests (repo-only) |
| `repo_tools/smoke-workflow.sh` | E2E smoke for repo maintainers |

`repo_tools/` contains repo-only CI/lint utilities; it is not part of the plugin.

## Slash Commands

| Command | Purpose | Arguments |
| --- | --- | --- |
| `/aidd-init` | Initialize workspace (`./aidd`) | `[--target <path>] [--force]` |
| `/idea-new` | Create PRD draft and questions | `<TICKET> [slug-hint] [note...]` |
| `/researcher` | Collect context and Researcher report | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/plan-new` | Plan + validation | `<TICKET> [note...]` |
| `/review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/spec-interview` | Spec interview (optional) | `<TICKET> [note...]` |
| `/tasks-new` | Build tasklist | `<TICKET> [note...]` |
| `/implement` | Iterative implementation | `<TICKET> [note...] [test=fast\|targeted\|full\|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/review` | Code review + tasks | `<TICKET> [note...]` |
| `/qa` | Final QA check | `<TICKET> [note...]` |
| `/status` | Ticket status and artifacts | `[<TICKET>]` |

## Prerequisites
- `bash`, `git`, `python3`.
- Claude Code with plugin marketplace access.
- Your stack build/test tools (optional).

macOS/Linux are supported. For Windows use WSL or Git Bash.

## Path Troubleshooting
- The plugin lives at the repo root (`commands/`, `agents/`, `hooks/`).
- Workspace artifacts are created in `./aidd` after `/aidd-init`.
- If commands or hooks cannot find the workspace, run `/aidd-init` or set `CLAUDE_PLUGIN_ROOT`.

## Documentation
- Core workflow overview: `aidd/docs/sdlc-flow.md` (after init).
- Deep dive and customization: `doc/dev/workflow.md`, `doc/dev/customization.md`.
- Agent and QA playbooks: `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`.
- Russian version: `README.md`.

## Contributing
Contribution guide: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
