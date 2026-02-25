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

_Last sync with `README.md`: 2026-02-25._

## What it is
AIDD is AI-Driven Development: the LLM works not as "one big brain" but as a team of roles inside your SDLC. The Claude Code plugin helps you move away from vibe-coding by capturing artifacts (PRD/plan/tasklist/reports), running quality gates, and adding agents, slash commands, hooks, and the `aidd/` structure.

Key features:
- Slash commands and agents for the idea → research → plan → review-spec → spec-interview (optional) → tasklist → implement → review → qa flow.
- Skill-first prompts: shared topology is split across `skills/aidd-core`, `skills/aidd-policy`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, `skills/aidd-rlm`, and `skills/aidd-stage-research` (EN); stage entrypoints are defined by stage skills.
- Research is required before planning: `research-check` expects status `reviewed`.
- PRD/Plan Review/QA gates and safe hooks (stage-aware).
- Rolling context pack (pack-first): `aidd/reports/context/<ticket>.pack.md`.
- Memory v2 (breaking-only): `semantic.pack` + `decisions.pack` as external context, with decision writes through validated actions.
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
- Breaking cleanup (February 21, 2026): removed deprecated `skills/aidd-core/runtime/researcher_context.py`, removed `--answers` alias from `spec-interview`, removed `--refresh` alias from `review/context_pack`, and removed deprecated `reports_pack` context-pack APIs.
- Large runtime entrypoints (`loop_*`, `tasklist_check`, `tasks_derive`, `reports_pack`, `qa`) now use thin facades with implementations moved to `runtime/*_parts/core.py`.
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
/feature-dev-aidd:idea-new STORE-123 "Checkout: discounts, coupons, double-charge protection"
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
- `slug_hint` is auto-generated inside `/feature-dev-aidd:idea-new` from `note` (LLM summary -> slug token); users should not pass it manually.
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
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py --ticket <ticket>` | Build semantic memory pack |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py --ticket <ticket> --topic "<topic>" --decision "<decision>"` | Append one item to the decisions log |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py --ticket <ticket>` | Rebuild decisions pack |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_slice.py --ticket <ticket> --query "<token>"` | Build targeted memory slice pack |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_autoslice.py --ticket <ticket> --stage <stage> --scope-key <scope_key> --format json` | Build stage-aware memory slice manifest (`memory-slices.<stage>.<scope_key>.pack.json`) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_verify.py --input <artifact.json-or-jsonl>` | Validate memory schema + budgets |
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
| `/feature-dev-aidd:idea-new` | Create PRD draft and questions | `<TICKET> [note...]` |
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

Migration policy (legacy -> RLM-only):
- Legacy pre-RLM research context/targets artifacts are not used by runtime/gates.
- For older workspace artifacts, regenerate research with:
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto`.
- If `rlm_status=pending`, hand off to the shared owner:
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`.
- Plan/review/qa readiness requires the minimal RLM set:
  `rlm-targets`, `rlm-manifest`, `rlm.worklist.pack`, `rlm.nodes`, `rlm.links`, `rlm.pack`.

RLM artifacts (pack-first):
- Pack summary: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice tool: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>" [--paths path1,path2] [--lang kt,java]`.
- RLM pack budget: `config/conventions.json` → `rlm.pack_budget` (`max_chars`, `max_lines`, top-N limits).

## Memory v2 + Slice Enforcement (breaking-only)

Memory v2 is enabled in Wave 101 as a **breaking-only** contract:
- no backfill of legacy memory state;
- no fallback to legacy memory artifacts;
- source of truth is `aidd/reports/memory/<ticket>.semantic.pack.json` and `aidd/reports/memory/<ticket>.decisions.pack.json`.

Wave 102 adds stage-aware lightweight memory artifacts:
- `aidd/reports/memory/<ticket>.decisions.jsonl` (append-only log);
- `aidd/reports/context/<ticket>-memory-slices.<stage>.<scope_key>.pack.json` (manifest);
- `aidd/reports/context/<ticket>-memory-slice-<hash>.pack.json` + alias `...memory-slice.<stage>.<scope_key>.latest.pack.json`.

Recommended read order (pack-first):
1. `aidd/reports/research/<ticket>-rlm.pack.json`
1. `aidd/reports/research/<ticket>-ast.pack.json` (optional)
1. `aidd/reports/memory/<ticket>.semantic.pack.json`
1. `aidd/reports/memory/<ticket>.decisions.pack.json`
1. `aidd/reports/context/<ticket>-memory-slices.<stage>.<scope_key>.pack.json`
1. specific chunk/slice artifacts (`*-memory-slice-*.pack.json`, `rlm_slice`, `chunk_query`)
1. `aidd/reports/context/<ticket>.pack.md` and full-read fallback (only with reason codes)

Decision writes must go through the validated path (`memory_ops.decision_append`), not direct JSONL edits.
After `memory_ops.decision_append`, runtime rebuilds `decisions.pack` in the same execution; stale windows are reported via `memory_decisions_pack_stale`.

`rg` policy:
1. default is `memory.slice_enforcement=warn` with `memory.rg_policy=controlled_fallback`;
1. `rg` is allowed only after a fresh memory slice manifest attempt (otherwise `rg_without_slice`, `ask/deny` by mode);
1. hard rollout is switched in `aidd/config/gates.json` after KPI readiness.

Diagnostics and telemetry:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py` evaluates `memory.rollout_hardening`;
- KPI artifact: `aidd/reports/observability/<ticket>.context-quality.json` (`memory_slice_reads`, `rg_invocations`, `rg_without_slice_rate`, `decisions_pack_stale_events`);
- rollout thresholds are configured in `aidd/config/gates.json` → `memory.rollout_hardening`.

## AST Index (optional + fallback)

AST retrieval in Wave 101 is an optional dependency:
- minimal required dependencies stay unchanged: `python3`, `rg`, `git`;
- `ast-index` is enabled via `aidd/config/conventions.json` + `aidd/config/gates.json`.

Modes:
1. `off`: AST path is disabled.
1. `auto` (default): try `ast-index` first; on degradation, deterministic `rg` fallback with reason codes.
1. `required`: missing `ast-index` readiness or failed threshold policy blocks the stage (`BLOCKED`) with `next_action`.

Canonical AST artifact:
- `aidd/reports/research/<ticket>-ast.pack.json`

Normalized fallback reason codes:
- `ast_index_binary_missing`
- `ast_index_index_missing`
- `ast_index_timeout`
- `ast_index_json_invalid`
- `ast_index_fallback_rg`

Diagnostics and rollout gate:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py` validates:
  - `ast-index readiness` (optional/required semantics),
  - `ast-index wave-2 rollout` (threshold gate for expanding scope to `implement/review/qa`).
- Threshold contract is configured in `aidd/config/gates.json` → `ast_index.rollout_wave2`:
  - `decision_mode`: `advisory|hard`
  - `thresholds`: `quality_min`, `latency_p95_ms_max`, `fallback_rate_max`
  - `metrics_artifact`: `aidd/reports/observability/ast-index.rollout.json`

Example metrics artifact:

```json
{
  "quality_score": 0.82,
  "latency_p95_ms": 1800,
  "fallback_rate": 0.21
}
```

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
- Skill-first topology: `skills/aidd-core`, `skills/aidd-policy`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, `skills/aidd-rlm`, and `skills/aidd-stage-research` (EN).
- Russian version: `README.md`.

## Examples
Demo projects and helper scripts are not shipped — the repo stays language-agnostic. Keep demos outside the plugin and document them in your workspace docs if needed.

## Dev-only checks
- Repo checks (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Contributing
Contribution guide: `CONTRIBUTING.md`.

## License
MIT, see `LICENSE`.
