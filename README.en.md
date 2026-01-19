# AIDD Claude Code Plugin - Language-agnostic Workflow Template

> A ready-to-use Claude Code plugin: slash commands, agents, hooks, and templates for the idea → research → plan → review-spec → spec-interview (optional) → tasklist → implement → review → qa flow.

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

_Last sync with `README.md`: 2026-01-18._

## What it is
AIDD is AI-Driven Development: the LLM works not as "one big brain" but as a team of roles inside your SDLC. The Claude Code plugin helps you move away from vibe-coding by capturing artifacts (PRD/plan/tasklist/reports), running quality gates, and adding agents, slash commands, hooks, and the `aidd/` structure.

Key features:
- Slash commands and agents for the idea → research → plan → review-spec → spec-interview (optional) → tasklist → implement → review → qa flow.
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
/feature-dev-aidd:aidd-init
```

For CI or manual use:

```bash
${CLAUDE_PLUGIN_ROOT}/tools/init.sh
```

### 3. Run a feature in Claude Code

```text
/feature-dev-aidd:idea-new STORE-123 checkout-discounts
/feature-dev-aidd:researcher STORE-123
/feature-dev-aidd:plan-new STORE-123
/feature-dev-aidd:review-spec STORE-123
/feature-dev-aidd:spec-interview STORE-123
/feature-dev-aidd:tasks-new STORE-123
/feature-dev-aidd:implement STORE-123
/feature-dev-aidd:review STORE-123
/feature-dev-aidd:qa STORE-123
```

Notes:
- Questions can appear after `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:review-spec`, and `/feature-dev-aidd:spec-interview` (if you run it).
- Answer in `AIDD:ANSWERS` (`Answer N` format) in response to the same command that asked the questions; keep `AIDD:OPEN_QUESTIONS` synced as `Q1/Q2/...` — when `AIDD:OPEN_QUESTIONS` is present, `analyst-check` blocks mismatches. In the plan, reference `PRD QN` instead of duplicating questions.

## Scripts and Checks

| Command | Description |
| --- | --- |
| `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` | Create `./aidd` from templates (no overwrite) |
| `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh` | Diagnose environment, paths, and `aidd/` presence |
| `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket>` | Generate research context |
| `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket <ticket>` | Verify Research status `reviewed` |
| `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` | Verify PRD `READY` and Q/A sync |
| `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source <stage> --ticket <ticket>` | Confirm tasklist progress |
| `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Run QA report + gate |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket <ticket>` | Validate tasklist contract |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source <qa\|research\|review> --append --ticket <ticket>` | Append handoff tasks |
| `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket <ticket> [--refresh]` | Ticket status summary (stage/artifacts/events) |
| `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh --ticket <ticket>` | Refresh ticket index `aidd/docs/index/<ticket>.yaml` |
| `tests/repo_tools/ci-lint.sh` | CI linters + unit tests (repo-only) |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke for repo maintainers |

`tests/repo_tools/` contains repo-only CI/lint utilities; it is not part of the plugin.

## Slash Commands

| Command | Purpose | Arguments |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Initialize workspace (`./aidd`) | `[--force]` |
| `/feature-dev-aidd:idea-new` | Create PRD draft and questions | `<TICKET> [slug-hint] [note...]` |
| `/feature-dev-aidd:researcher` | Collect context and Researcher report | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/feature-dev-aidd:plan-new` | Plan + validation | `<TICKET> [note...]` |
| `/feature-dev-aidd:review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/feature-dev-aidd:spec-interview` | Spec interview (optional) | `<TICKET> [note...]` |
| `/feature-dev-aidd:tasks-new` | Build tasklist | `<TICKET> [note...]` |
| `/feature-dev-aidd:implement` | Iterative implementation | `<TICKET> [note...] [test=fast\|targeted\|full\|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/feature-dev-aidd:review` | Code review + tasks | `<TICKET> [note...]` |
| `/feature-dev-aidd:qa` | Final QA check | `<TICKET> [note...]` |
| `/feature-dev-aidd:status` | Ticket status and artifacts | `[<TICKET>]` |

## Research Call Graph

| Scenario | Graph required | Mode |
| --- | --- | --- |
| Kotlin/Java (kt/kts/java) | Yes | `--auto` (focus) |
| Mixed repo with JVM modules | Yes (for JVM) | `--auto` |
| Non‑JVM (py/js/go/etc.) | No | fast-scan |
| Thin context/unclear dependencies | Recommended | `--graph-mode full` |

WARN/INSTALL_HINT examples:
- `[aidd] WARN: 0 matches for <ticket> — narrow paths/keywords or run graph-only.`
- `[aidd] INSTALL_HINT: python3 -m pip install tree_sitter_language_pack`
- `[aidd] WARN: tree-sitter not available: ...`

Empty context troubleshooting:
- Narrow `--paths`/`--keywords` (point to real code, not only `aidd/`).
- Run graph-only: `--call-graph --graph-mode full`.
- Use `--paths-relative workspace` if code lives outside `aidd/`.
- Install `tree_sitter_language_pack` if call graph is empty.

## Prerequisites
- `bash`, `git`, `python3`.
- Claude Code with plugin marketplace access.
- Your stack build/test tools (optional).

macOS/Linux are supported. For Windows use WSL or Git Bash.

## Path Troubleshooting
- The plugin lives at the repo root (`commands/`, `agents/`, `hooks/`).
- Workspace artifacts are created in `./aidd` after `/feature-dev-aidd:aidd-init`.
- If commands or hooks cannot find the workspace, run `/feature-dev-aidd:aidd-init` or set `CLAUDE_PLUGIN_ROOT`.
- For a quick environment check, run `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh`.

## Documentation
- Core workflow overview: `aidd/docs/sdlc-flow.md` (after init).
- Deep dive and customization: `AGENTS.md`.
- Russian version: `README.md`.

## Dev-only checks
- Repo checks (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Contributing
Contribution guide: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
