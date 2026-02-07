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
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)

## Sync Guide
- Always edit `README.md` (RU) first, then update this translation in the same commit.
- Mirror section structure, headlines, and links.
- Update the date below whenever both files are aligned.

_Last sync with `README.md`: 2026-02-07._

## What it is
AIDD is AI-Driven Development: the LLM works not as "one big brain" but as a team of roles inside your SDLC. The Claude Code plugin helps you move away from vibe-coding by capturing artifacts (PRD/plan/tasklist/reports), running quality gates, and adding agents, slash commands, hooks, and the `aidd/` structure.

Key features:
- Slash commands and agents for the idea → research → plan → review-spec → spec-interview (optional) → tasklist → implement → review → qa flow.
- Skill-first prompts: canonical runtime/output policy lives in `skills/aidd-core` and `skills/aidd-loop` (EN); stage entrypoints are defined by skills.
- Research is required before planning: `research-check` expects status `reviewed`.
- PRD/Plan Review/QA gates and safe hooks (stage-aware).
- Rolling context pack (pack-first): `aidd/reports/context/<ticket>.pack.md`.
- Hooks mode: default `AIDD_HOOKS_MODE=fast`, strict mode via `AIDD_HOOKS_MODE=strict`.
- Auto-formatting + stage test policy: `implement` — no tests, `review` — targeted, `qa` — full.
- Loop mode implement↔review: loop pack/review pack, diff boundary guard, loop-step/loop-run.
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

`/feature-dev-aidd:aidd-init` creates `./aidd` and `.claude/settings.json` with default `automation.tests`. To refresh/detect stack-specific defaults, run:

```text
/feature-dev-aidd:aidd-init --detect-build-tools
```

Additional flags:
- `--enable-ci` adds a workspace GitHub Actions scaffold (`.github/workflows/aidd-manual.yml`).
- `--dry-run` prints planned changes without writing files.

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

### Workspace updates
- `/feature-dev-aidd:aidd-init` without `--force` adds new artifacts and preserves existing files.
- Use `--force` or manual template sync when you need updates.
- Root `AGENTS.md` is the repo dev guide; the user workflow guide is `aidd/AGENTS.md` (copied from `templates/aidd/AGENTS.md`).

## Scripts and Checks

| Command | Description |
| --- | --- |
| `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` | Create `./aidd` from templates (no overwrite) |
| `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh` | Diagnose environment, paths, and `aidd/` presence |
| `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket>` | Generate research context |
| `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket <ticket>` | Verify Research status `reviewed` |
| `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` | Verify PRD `READY` and Q/A sync |
| `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source <stage> --ticket <ticket>` | Confirm tasklist progress |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket <ticket> --stage implement\|review` | Generate loop pack for current work item |
| `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-report.sh --ticket <ticket> --findings-file <path> --status warn` | Generate review report |
| `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh --ticket <ticket>` | Generate review pack (thin feedback) |
| `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/reviewer-tests.sh --ticket <ticket> --status required\|optional` | Update reviewer marker for test policy |
| `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket <ticket>` | Validate diff against loop-pack allowed paths |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` | Single loop step (implement↔review) |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5` | Auto-loop until all open iterations are complete |
| `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Run QA report + gate |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket <ticket>` | Validate tasklist contract |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source <qa\|research\|review> --append --ticket <ticket>` | Append handoff tasks |
| `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket <ticket> [--refresh]` | Ticket status summary (stage/artifacts/events) |
| `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh --ticket <ticket> --stage <implement\|review\|qa>` | Final status from stage_result (single source) |
| `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh --ticket <ticket>` | Refresh ticket index `aidd/docs/index/<ticket>.json` |
| `tests/repo_tools/ci-lint.sh` | CI linters + unit tests (repo-only) |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke for repo maintainers |

`tests/repo_tools/` contains repo-only CI/lint utilities; it is not part of the plugin.

`tools/review-report.sh`, `tools/review-pack.sh`, and `tools/reviewer-tests.sh` remain deprecated compatibility shims and emit warnings.

## Slash Commands

| Command | Purpose | Arguments |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Initialize workspace (`./aidd`) | `[--force] [--detect-build-tools] [--enable-ci] [--dry-run]` |
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

## Research RLM
RLM evidence is the primary integration/risks source (pack-first + slice on demand).

Empty context troubleshooting:
- Narrow `--paths`/`--keywords` (point to real code, not only `aidd/`).
- Use `--paths-relative workspace` if code lives outside `aidd/`.
- If `rlm_status=pending`, complete the agent worklist flow and rebuild the RLM pack.

RLM artifacts (pack-first):
- Pack summary: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice tool: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>" [--paths path1,path2] [--lang kt,java]`.
- `*-context.pack.json` budget: `config/conventions.json` → `reports.research_pack_budget` (defaults: `max_chars=2000`, `max_lines=120`).

## Loop mode (implement↔review)

Loop = 1 work_item → implement → review → (revise)* → ship.
If open iterations remain in `AIDD:NEXT_3`/`AIDD:ITERATIONS_FULL` after SHIP, loop-run selects the next work item, updates `aidd/docs/.active.json` (work_item/stage), and continues with implement.

Key artifacts:
- `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md` — thin iteration context.
- `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` — short feedback with verdict.

Commands:
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Bash loop: `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` (fresh sessions).
- One-shot: `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5`.
- Scope guard: `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket <ticket>`.
- Stream (optional): `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket> --stream=text|tools|raw`,
  `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --stream`.

Example from the project root:
```bash
CLAUDE_PLUGIN_ROOT="/path/to/ai_driven_dev" "$CLAUDE_PLUGIN_ROOT/tools/loop-run.sh" --ticket ABC-123 --max-iterations 5
```

Note:
- Ralph plugin uses a stop-hook in the same session (completion promise). AIDD loop-mode uses fresh sessions.
- Use the space form for max-iterations: `--max-iterations 5` (no `=`).
- If `CLAUDE_PLUGIN_ROOT`/`AIDD_PLUGIN_DIR` is not set, loop scripts attempt auto-detect from the script path and emit WARN; if auto-detect fails they block.
- Stream logs: `aidd/reports/loops/<ticket>/cli.loop-*.stream.log` (human) and `aidd/reports/loops/<ticket>/cli.loop-*.stream.jsonl` (raw).
- Loop run log: `aidd/reports/loops/<ticket>/loop.run.log`.
- Cadence/tests settings live in `.claude/settings.json` at the workspace root (no `aidd/.claude`).

Rules:
- Loop pack first, no large log/diff pastes (use `aidd/reports/**` links).
- Review does not expand scope: new work → `AIDD:OUT_OF_SCOPE_BACKLOG` or new work item.
- Review pack is required; if review report + loop pack exist it can be regenerated.
- Final Status in implement/review/qa must match `stage_result`.
- Allowed paths come from `Expected paths` per iteration (`AIDD:ITERATIONS_FULL`).
- Loop-mode tests follow stage policy: `implement` — no tests, `review` — targeted, `qa` — full.
- Tests evidence: `tests_log` with `status=skipped` + `reason_code` counts as evidence for `tests_required=soft` (for `hard` → BLOCKED).

## Prerequisites
- `bash`, `git`, `python3`.
- Claude Code with plugin marketplace access.
- Your stack build/test tools (optional).
- MCP integrations are optional; `.mcp.json` is not shipped by default.

macOS/Linux are supported. For Windows use WSL or Git Bash.

## Path Troubleshooting
- The plugin lives at the repo root (`agents/`, `skills/`, `hooks/`, `tools/`).
- Workspace artifacts are created in `./aidd` after `/feature-dev-aidd:aidd-init`.
- If commands or hooks cannot find the workspace, run `/feature-dev-aidd:aidd-init` or set `CLAUDE_PLUGIN_ROOT`.
- For a quick environment check, run `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh`.

## Documentation
- Canonical response and pack-first rules: `aidd/docs/prompting/conventions.md`.
- User guide (runtime): `aidd/AGENTS.md`; repo dev guide: `AGENTS.md`.
- Skill-first canon: `skills/aidd-core` and `skills/aidd-loop` (EN).
- Russian version: `README.md`.

## Examples
Demo projects and helper scripts are not shipped — the repo stays language-agnostic. Keep demos outside the plugin and document them in your workspace docs if needed.

## Dev-only checks
- Repo checks (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Contributing
Contribution guide: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
