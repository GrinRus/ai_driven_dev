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

_Last sync with `README.md`: 2026-02-09._

## What it is
AIDD is AI-Driven Development: the LLM works not as "one big brain" but as a team of roles inside your SDLC. The Claude Code plugin helps you move away from vibe-coding by capturing artifacts (PRD/plan/tasklist/reports), running quality gates, and adding agents, slash commands, hooks, and the `aidd/` structure.

Key features:
- Slash commands and agents for the idea → research → plan → review-spec → spec-interview (optional) → tasklist → implement → review → qa flow.
- Skill-first prompts: shared topology is split across `skills/aidd-core`, `skills/aidd-policy`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, and `skills/aidd-rlm` (EN); stage entrypoints are defined by stage skills.
- Research is required before planning: `research-check` expects status `reviewed`.
- PRD/Plan Review/QA gates and safe hooks (stage-aware).
- Rolling context pack (pack-first): `aidd/reports/context/<ticket>.pack.md`.
- Hooks mode: default `AIDD_HOOKS_MODE=fast`, strict mode via `AIDD_HOOKS_MODE=strict`.
- Auto-formatting + stage test policy: `implement` — no tests, `review` — targeted, `qa` — full.
- Loop mode implement↔review: loop pack/review pack, diff boundary guard, loop-step/loop-run.
- Unified `AIDD:ANSWERS` format plus Q identifiers in `AIDD:OPEN_QUESTIONS` (the plan references `PRD QN` without duplication).
- Branch and commit conventions via `aidd/config/conventions.json`.

## SKILL-first runtime path policy
- Stage/shared runtime entrypoints (canonical): `python3 skills/*/runtime/*.py` (Python-only canon as of February 9, 2026).
- Runtime wrappers in `skills/*/scripts/*.sh` are removed.
- Hooks may keep shell entrypoints as platform glue (`hooks/*`).
- `tools/*` is used only for import stubs and repo-only tooling.
- Canonical runtime API lives in `skills/*/runtime/*.py`; `tools/*.sh` are retired.
- Starting February 9, 2026, new integrations must call Python entrypoints (`skills/*/runtime/*.py`) with `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}`.
- Rollback criteria: if cutover breaks `tests/repo_tools/ci-lint.sh` or `tests/repo_tools/smoke-workflow.sh`, temporary wrapper fallback is allowed for the impacted entrypoint with a mandatory follow-up task.
- Stage lexicon: public stage `review-spec` acts as an umbrella for internal `review-plan` and `review-prd`.

## SKILL authoring contract
- Cross-agent canon: `docs/agent-skill-best-practices.md`.
- Language/lint policy: `docs/skill-language.md` + `tests/repo_tools/lint-prompts.py`.
- User-invocable stage skills must include a `## Command contracts` section (interface-only cards: `When to run`, `Inputs`, `Outputs`, `Failure mode`, `Next action`).
- Do not retell implementation details in `SKILL.md`; move deep guidance to supporting files.
- `## Additional resources` must implement progressive disclosure with explicit `when:` + `why:` on each resource entry.

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

For CI or manual use:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py
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
- Source of truth: stage content templates live in `skills/*/templates/*`; `templates/aidd/**` keeps bootstrap config/placeholders only.
- Root `AGENTS.md` is the repo dev guide; the user workflow guide is `aidd/AGENTS.md` (copied from `skills/aidd-core/templates/workspace-agents.md`).

## Scripts and Checks

> The commands below are canonical Python runtime API entrypoints.

| Command | Description |
| --- | --- |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py` | Create `./aidd` from templates (no overwrite) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py` | Diagnose environment, paths, and `aidd/` presence |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket>` | Generate RLM-only research artifacts |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py --ticket <ticket>` | Verify Research status `reviewed` |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>` | Verify PRD `READY` and Q/A sync |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py --source <stage> --ticket <ticket>` | Confirm tasklist progress |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py --ticket <ticket> --stage implement\|review` | Generate loop pack for current work item |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_report.py --ticket <ticket> --findings-file <path> --status warn` | Generate review report |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py --ticket <ticket>` | Generate review pack (thin feedback) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py --ticket <ticket> --status required\|optional` | Update reviewer marker for test policy |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py --ticket <ticket>` | Validate diff against loop-pack allowed paths |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket>` | Single loop step (implement↔review) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --max-iterations 5` | Auto-loop until all open iterations are complete |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Run QA report + gate |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py --ticket <ticket>` | Validate tasklist contract |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py --source <qa\|research\|review> --append --ticket <ticket>` | Append handoff tasks |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py --ticket <ticket> [--refresh]` | Ticket status summary |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/status_summary.py --ticket <ticket> --stage <implement\|review\|qa>` | Final status from stage_result (single source) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py --ticket <ticket>` | Refresh ticket index |
| `tests/repo_tools/ci-lint.sh` | CI linters + unit tests (repo-only) |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke for repo maintainers |

`tests/repo_tools/` contains repo-only CI/lint utilities; it is not part of the plugin.

`review` runtime commands are canonical at `skills/review/runtime/*`.

CI required-check parity:
- Required: `lint-and-test`, `smoke-workflow`, `dependency-review`.
- Security rollout: `security-secret-scan` and `security-sast` are advisory while `AIDD_SECURITY_ENFORCE!=1`; they become required when `AIDD_SECURITY_ENFORCE=1`.

### Shared Ownership Map
- `skills/aidd-core/runtime/*` — shared core runtime API (canonical).
- `skills/aidd-docio/runtime/*` — shared DocIO runtime API (`md_*`, `actions_*`, `context_*`).
- `skills/aidd-flow-state/runtime/*` — shared flow/state runtime API (`set-active-*`, `progress*`, `tasklist*`, `stage_result`, `status_summary`, `prd_check`, `tasks_derive`).
- `skills/aidd-observability/runtime/*` — shared observability runtime API (`doctor`, `tools_inventory`, `tests_log`, `dag_export`, `identifiers`).
- `skills/aidd-loop/runtime/*` — shared loop runtime API (canonical).
- `skills/<stage>/runtime/*` — stage-local runtime API (single owner per stage).
- `tools/*.sh` are removed from runtime API.

## Slash Commands

| Command | Purpose | Arguments |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Initialize workspace (`./aidd`) | `[--force] [--detect-build-tools]` |
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
- If `rlm_status=pending`, complete the agent worklist flow and rebuild the RLM pack.

RLM artifacts (pack-first):
- Pack summary: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice tool: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>" [--paths path1,path2] [--lang kt,java]`.
- RLM pack budget: `config/conventions.json` → `rlm.pack_budget` (`max_chars`, `max_lines`, top-N limits).

## Loop mode (implement↔review)

Loop = 1 work_item → implement → review → (revise)* → ship.
If open iterations remain in `AIDD:NEXT_3`/`AIDD:ITERATIONS_FULL` after SHIP, loop-run selects the next work item, updates `aidd/docs/.active.json` (work_item/stage), and continues with implement.

Key artifacts:
- `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md` — thin iteration context.
- `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` — short feedback with verdict.

Commands:
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Loop CLI: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket>` (fresh sessions).
- One-shot: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --max-iterations 5`.
- Scope guard: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py --ticket <ticket>`.
- Stream (optional): `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket> --stream=text|tools|raw`,
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --stream`.

Example from the project root:
```bash
CLAUDE_PLUGIN_ROOT="/path/to/ai_driven_dev" PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python3 "$CLAUDE_PLUGIN_ROOT/skills/aidd-loop/runtime/loop_run.py" --ticket ABC-123 --max-iterations 5
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
- For a quick environment check, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`.

## Documentation
- Canonical response and pack-first rules: `aidd/AGENTS.md` + `skills/aidd-policy/SKILL.md`.
- User guide (runtime): `aidd/AGENTS.md`; repo dev guide: `AGENTS.md`.
- Skill-first topology: `skills/aidd-core`, `skills/aidd-policy`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, and `skills/aidd-rlm` (EN).
- Russian version: `README.md`.

## Examples
Demo projects and helper scripts are not shipped — the repo stays language-agnostic. Keep demos outside the plugin and document them in your workspace docs if needed.

## Dev-only checks
- Repo checks (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Contributing
Contribution guide: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
