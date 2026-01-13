# Claude Code Workflow - Language-agnostic Workflow Template

> Turn any repository into a Claude Code powered workspace with slash commands, safe hooks, stage-aware gates, and selective checks.

## Table of Contents
- [What it is](#what-it-is)
- [Get Started](#get-started)
- [CLI Reference](#cli-reference)
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

_Last sync with `README.md`: 2026-01-12._

## What it is
Claude Code Workflow adds a ready-to-use development process with agents and gates. You get the `aidd/` structure, slash commands, and a consistent way to manage PRDs, plans, and tasklists.

Key features:
- Slash commands and agents for the idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa flow.
- Research is required before planning: `research-check` expects status `reviewed`.
- PRD/Plan Review/QA gates and safe hooks (stage-aware).
- Auto-formatting and selective tests during the `implement` stage.
- Branch and commit conventions via `config/conventions.json`.

## Get Started

### 1. Install the CLI

**Option A - uv (recommended)**

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
```

**Option B - pipx**

```bash
pipx install git+https://github.com/GrinRus/ai_driven_dev.git
```

**Option C - local script**

```bash
PAYLOAD_ROOT="/path/to/ai_driven_dev/src/claude_workflow_cli/data/payload/aidd"
mkdir -p aidd
(cd aidd && bash "${PAYLOAD_ROOT}/init-claude-workflow.sh" --commit-mode ticket-prefix --enable-ci)
```

### 2. Initialize the workspace

```bash
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
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
- After `/idea-new`, answer the analyst questions and update the PRD to `Status: READY` (check with `claude-workflow analyst-check --ticket STORE-123`).
- `/review-spec` performs plan review and PRD review in one step.

## CLI Reference

| Command | Description |
| --- | --- |
| `claude-workflow init --target .` | Bootstrap workspace and payload into `./aidd` |
| `claude-workflow sync` | Refresh `.claude/` (use `--include .claude-plugin` for the plugin) |
| `claude-workflow upgrade --force` | Overwrite artifacts |
| `claude-workflow smoke` | End-to-end smoke workflow |
| `claude-workflow research --ticket <ticket>` | Generate research context |
| `claude-workflow research-check --ticket <ticket>` | Verify Research status `reviewed` |
| `claude-workflow analyst-check --ticket <ticket>` | Verify PRD status `READY` |
| `claude-workflow qa --ticket <ticket> --gate` | Run QA report + gate |
| `claude-workflow progress --source <stage> --ticket <ticket>` | Confirm tasklist progress |

## Slash Commands

| Command | Purpose | Arguments |
| --- | --- | --- |
| `/idea-new` | Create PRD draft and questions | `<TICKET> [slug-hint] [note...]` |
| `/researcher` | Collect context and Researcher report | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/plan-new` | Plan + validation | `<TICKET> [note...]` |
| `/review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/tasks-new` | Build tasklist | `<TICKET> [note...]` |
| `/implement` | Iterative implementation | `<TICKET> [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/review` | Code review + tasks | `<TICKET> [note...]` |
| `/qa` | Final QA check | `<TICKET> [note...]` |

## Prerequisites
- `bash`, `git`, `python3`.
- `uv` or `pipx` for CLI installation.
- Your stack build/test tools (optional).

macOS/Linux are supported. For Windows use WSL or Git Bash.

## Path Troubleshooting
- All artifacts live under `aidd/` (docs, reports, hooks).
- If the CLI cannot locate files, run with `--target .` or from `aidd/`.
- For manual overrides, use `CLAUDE_PLUGIN_ROOT=./aidd`.

## Documentation
- Core workflow overview: `aidd/docs/sdlc-flow.md`.
- Deep dive and customization: `doc/dev/workflow.md`, `doc/dev/customization.md`.
- Agent and QA playbooks: `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`.
- Russian version: `README.md`.

## Contributing
Contribution guide: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
