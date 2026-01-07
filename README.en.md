# Claude Code Workflow — Language-agnostic Workflow Template

> Turn any repository into a Claude Code powered workspace with slash commands, safe hooks, stage-aware gates, and configurable checks (formatting/tests/linters).

## Sync Guide
- Always edit `README.md` (RU) first, then update this translation in the same commit.
- Mirror section structure, headlines, and links. Leave a note if a Russian-only section has no equivalent.
- Update the date below whenever both files are aligned.

_Last sync with `README.md`: 2026-01-06._  <!-- update when EN catches up -->

## TL;DR
- `claude-workflow init --target .` (or `aidd/init-claude-workflow.sh` from the payload) bootstraps `/idea-new (analyst) → research when needed → /plan-new → /review-spec (review-plan + review-prd) → /tasks-new → /implement → /review → /qa`; `claude-workflow sync|upgrade|smoke` cover payload refresh and smoke.
- Formatting and selective checks (`aidd/hooks/format-and-test.sh`) run only during the `implement` stage and only on Stop/SubagentStop (`SKIP_AUTO_TESTS=1` to pause); test profiles live in `aidd/.cache/test-policy.env`; `gate-*` hooks keep PRD/plan/tasklist/test gates enforced.
- The feature stage is stored in `aidd/docs/.active_stage` and updated by slash commands (`/idea-new`, `/plan-new`, `/review-spec`, `/tasks-new`, `/implement`, `/review`, `/qa`); you can roll back to any step.
- Configurable branch/commit conventions via `config/conventions.json` plus ready-to-use docs and prompt templates.
- Optional GitHub Actions, issue/PR templates, and Claude Code access policies.
- The payload lives in `aidd/` (`aidd/agents`, `aidd/commands`, `aidd/hooks`, `aidd/.claude-plugin`, `aidd/docs`, `aidd/config`); all artifacts/reports stay under `aidd/`. Workspace settings live at the root (`.claude/settings.json`, `.claude/cache/`, `.claude-plugin/marketplace.json`) — run CLI with `--target .` (workspace root) or from `aidd/` if tools cannot locate files.

## Table of Contents
- [CLI cheatsheet](#cli-cheatsheet)
- [What you get](#what-you-get)
- [Workflow architecture](#workflow-architecture)
- [Agent-first principles](#agent-first-principles)
- [Repository structure](#repository-structure)
- [Repository composition](#repository-composition)
- [Deep dive into components](#deep-dive-into-components)
- [Architecture & relationships](#architecture--relationships)
- [Key scripts and hooks](#key-scripts-and-hooks)
- [Test toolkit](#test-toolkit)
- [Access policies & gates](#access-policies--gates)
- [Docs & templates](#docs--templates)
- [Examples & demos](#examples--demos)
- [Installation](#installation)
  - [Option A — `uv tool install` (recommended)](#option-a--uv-tool-install-recommended)
  - [Option B — `pipx`](#option-b--pipx)
  - [Option C — local script](#option-c--local-script)
- [Prerequisites](#prerequisites)
- [Quick start in Claude Code](#quick-start-in-claude-code)
- [Feature kickoff checklist](#feature-kickoff-checklist)
- [Slash commands](#slash-commands)
- [Branch & commit modes](#branch--commit-modes)
- [Selective tests](#selective-tests)
- [Additional resources](#additional-resources)
- [Migration to agent-first](#migration-to-agent-first)
- [Contribution & license](#contribution--license)

## CLI cheatsheet
- `claude-workflow init --target . [--commit-mode ... --enable-ci]` — bootstrap into `./aidd`.
- `claude-workflow sync --include .claude --include .claude-plugin [--release latest]` / `claude-workflow upgrade [--force]` — refresh the payload without overwriting local edits (use `--force` to overwrite).
- `claude-workflow smoke` — e2e smoke (idea → plan → review-spec (review-plan + review-prd) → tasklist) with gates.
- `claude-workflow analyst-check --ticket <ticket>` — validate the analyst dialog/PRD status.
- `claude-workflow research --ticket <ticket> --auto --deep-code [--call-graph]` — collect targets, matches, and call graph.
- `claude-workflow reviewer-tests --status required|optional --ticket <ticket>` — toggle reviewer test marker.
- `claude-workflow tasks-derive --source qa|review|research --append --ticket <ticket>` — append handoff items to `aidd/docs/tasklist/<ticket>.md`.
- `claude-workflow qa --ticket <ticket> --gate` — QA agent + gate report.
- `claude-workflow progress --source implement|qa|review|handoff --ticket <ticket>` — assert new `- [x]`/handoff tasks before merging.

## What you get
- Claude Code slash commands and sub-agents to bootstrap PRD/ADR/Tasklist docs, generate updates, and validate commits.
- A multi-stage workflow (idea → research → plan → review-plan → review-prd → tasks → implementation → review → QA; can run `/review-spec`) powered by `analyst/researcher/planner/plan-reviewer/prd-reviewer/validator/implementer/reviewer/qa` sub-agents; additional gates are toggled via `config/gates.json`.
- Git hooks for auto-formatting, selective tests, and workflow guards (stage-aware by default).
- Commit convention presets (`ticket-prefix`, `conventional`, `mixed`) with documented templates for messages and branch names.
- Documentation pack, issue/PR templates, and optional CI workflow.
- Zero dependency on Spec Kit or BMAD — everything runs locally.

## Workflow architecture
1. `claude-workflow init --target .` (or `aidd/init-claude-workflow.sh` from the payload) scaffolds workspace `.claude/` and `.claude-plugin/`, and lays out the payload under `aidd/`.
2. Slash commands drive the multi-stage process (see `aidd/docs/sdlc-flow.md`, maintainer details in `doc/dev/agents-playbook.md`): idea, research, plan, review-plan, review-prd (or `/review-spec`), tasklist, implementation, and review with dedicated sub-agents.
3. The `feature-dev-aidd` plugin from `.claude-plugin/marketplace.json` wires pre/post hooks (`gate-*`, `format-and-test.sh`); `.claude/settings.json` only keeps permissions/automation and enables the plugin.
4. `aidd/hooks/format-and-test.sh` performs formatting and selective tests via `.claude/settings.json` and runs only during the `implement` stage (Stop/SubagentStop).
5. Policies and branch/commit presets are managed via `.claude/settings.json` and `config/conventions.json`.

## Agent-first principles
- **Slug-hint and repository first, questions later.** Analyst starts with the slug-hint stored in `aidd/docs/.active_feature`, then reads `aidd/docs/research/<ticket>.md`, `reports/research/*.json` (`code_index`/`reuse_candidates`), and existing plans before creating any Q&A. Researcher records every command (`claude-workflow research --auto --deep-code`, `rg "<ticket>" src/**`, `find`, `python`) and builds the call/import graph with Claude Code; implementer updates the tasklist plus lists executed test/lint commands and `claude-workflow progress` runs before pinging the user.
- **Commands & logs are part of the answer.** Prompts and templates now require documenting allowed CLI invocations (your test runner, `rg`, `claude-workflow`) and attaching logs/paths so downstream agents can reproduce the steps. Tasklist and research templates include explicit `Commands/Reports` sections.
- **Auto-generated artifacts.** `/idea-new` scaffolds PRD, triggers the analyst (research is on-demand when context is thin), and instructs the analyst to mine repository data. The `doc/dev/templates/prompts/prompt-agent.md` / `doc/dev/templates/prompts/prompt-command.md` templates describe how to document inputs, gates, commands, and fail-fast rules in an agent-first style.

Advanced customization tips are covered in `doc/dev/workflow.md` and `doc/dev/customization.md`.

## Repository structure
| Path | Purpose | Highlights |
| --- | --- | --- |
| `.claude/settings.json` | Access & automation policies | `start`/`strict` presets, allow/ask/deny, automation; pre/post hooks live in the plugin (`hooks/hooks.json`) |
| `aidd/commands/` | Slash-command definitions | Workflows for `/idea-new`, `/researcher`, `/plan-new`, `/review-spec`, `/tasks-new`, `/implement`, `/review`, `/qa` with `allowed-tools` and inline shell steps |
| `aidd/agents/` | Sub-agent playbooks | Roles for analyst, researcher, planner, plan-reviewer, prd-reviewer, validator, implementer, reviewer, qa |
| `aidd/hooks/` | Guard & utility hooks | `gate-workflow.sh`, `gate-prd-review.sh`, `gate-tests.sh`, `gate-qa.sh`, `lint-deps.sh`, `format-and-test.sh` |
| `config/gates.json` | Gate toggles | Controls `prd_review`, `tests_required`, `deps_allowlist`, `qa`, `feature_ticket_source`, `feature_slug_hint_source` (uses `aidd/docs/.active_*`) |
| `config/conventions.json` | Branch/commit presets | Detailed `ticket-prefix`, `conventional`, `mixed` templates plus branch patterns and review notes |
| `config/allowed-deps.txt` | Dependency allowlist | `group:artifact` entries inspected by `lint-deps.sh` |
| `aidd/docs/` | Core docs & templates | `sdlc-flow.md`, `status-machine.md`, `docs/*/template.md`, feature artefacts |
| `examples/` | Demo assets | `apply-demo.sh` and baseline examples |
| `doc/dev/` | Dev-only docs | Workflow walkthrough, playbooks (agents/qa/prompt), customization, audits, design notes |
| `scripts/` | CLI helpers | `ci-lint.sh` (linters + tests), `smoke-workflow.sh` (E2E smoke for gate-workflow), `sync-payload.sh` (payload sync), `prompt-version`/`lint-prompts.py` (prompt tooling), `package_payload_archive.py` (payload archive) |
| `templates/` | Copyable templates | Git hooks (`commit-msg`, `pre-push`, `prepare-commit-msg`) |
| `tests/` | Python unit tests | Cover init bootstrap, hooks, selective tests, and settings policy |
| `.github/workflows/ci.yml` | CI pipeline | Installs linters and runs `scripts/ci-lint.sh` |
| `aidd/init-claude-workflow.sh` | Bootstrap script | Flags `--commit-mode`, `--enable-ci`, `--force`, `--dry-run`; dependency detection |

## Repository composition
- **Runtime (user workspace):** `aidd/**` plus root `.claude/` and `.claude-plugin/` after `claude-workflow init`.
- **Dev-only (this repo):** `doc/dev/`, `tests/`, `examples/`, `tools/`, `scripts/`, `.github/`, `.dev/`, `.tmp-debug/`, `build/` — excluded from the payload.
- **Where to look:** core runtime docs/templates live in `aidd/docs/**`, detailed playbooks live in `doc/dev/`.

## Deep dive into components

### Bootstrap & utilities
- `aidd/init-claude-workflow.sh` — modular bootstrap with strict prerequisite checks (`bash/git/python3`), `--commit-mode/--enable-ci/--force/--dry-run`, generation of `.claude/`, `.claude-plugin/`, and `aidd/**`, plus automatic commit-mode updates.
- `scripts/ci-lint.sh` — single entrypoint for `shellcheck`, `markdownlint`, `yamllint`, and `python -m unittest`; gracefully skips missing linters and is wired into CI.
- `scripts/smoke-workflow.sh` — E2E smoke scenario: spins a temp project, runs the bootstrap, walks the ticket-first loop (`ticket → PRD → plan → review-spec → tasklist`), and asserts `gate-workflow.sh`/`tasklist_progress` behaviour (changes without new `- [x]` are blocked).
- `examples/apply-demo.sh` — demonstrates applying the bootstrap to a demo project, prints before/after trees, and runs checks when configured.
- The bootstrap provisions `aidd/hooks/*` and documentation; branch and commit flows rely on native git commands guided by `config/conventions.json`.

### Hooks & automation
- `aidd/hooks/format-and-test.sh` — Python hook reading `.claude/settings.json`, honouring `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, `AIDD_TEST_PROFILE/TASKS/FILTERS/FORCE`, inspecting `git diff` plus the active ticket/slug hint, selecting a profile (fast/targeted/full/none), resolving tasks via `fastTasks/fullTasks/targetedTask`, `moduleMatrix`, `defaultTasks`, `fallbackTasks`, and caching fingerprints in `aidd/.cache/format-and-test.last.json`. Runs on Stop/SubagentStop and only during the `implement` stage.
- `aidd/hooks/gate-workflow.sh` — blocks edits under `src/**` until the active ticket has PRD, plan, `## Plan Review`, `## PRD Review` with `Status: READY`, and fresh `- [x]` entries in `aidd/docs/tasklist/<ticket>.md` (the `tasklist_progress` gate), while ignoring documentation/template edits.
- `aidd/hooks/gate-prd-review.sh` — enforces PRD review readiness: inspects the active PRD, ensures the review section exists, and prevents merging when blockers remain.
- `aidd/hooks/gate-tests.sh` — optional check driven by `config/gates.json`, validating the presence of matching tests (`disabled|soft|hard`) with actionable hints; test folders are excluded by default via `exclude_dirs`.
- `aidd/hooks/lint-deps.sh` — monitors dependency changes, validates them against `config/allowed-deps.txt`, and reports drift.

### Claude Code sub-agents
- `aidd/agents/analyst.md` — turns raw ideas into PRDs, asks clarifying questions, tracks risks/assumptions, and updates `aidd/docs/prd/<ticket>.prd.md` with READY/BLOCKED status.
- `aidd/agents/planner.md` — produces `aidd/docs/plan/<ticket>.md` with DoD and dependencies; `aidd/agents/validator.md` audits the plan and records follow-up questions for product/architecture.
- `aidd/agents/plan-reviewer.md` — checks plan executability, updates `## Plan Review`, sets READY/BLOCKED, and records blockers.
- `aidd/agents/prd-reviewer.md` — performs structured PRD audits, verifies metrics/risks, fills `## PRD Review` (status, summary, findings, action items), and hands blockers back to product.
- `aidd/agents/implementer.md` — guides iterative delivery, tracks gate status, updates tasklists (`Checkbox updated: …`, new `- [x]`), and calls `claude-workflow progress --source implement` in between iterations.
- `aidd/agents/reviewer.md` — summarizes review findings, checks tasklists, flips READY/BLOCKED, records follow-up tasks in `aidd/docs/tasklist/<ticket>.md`, and runs `claude-workflow progress --source review` before handing off.
- `aidd/agents/qa.md` — final QA sweep; produces severity-tagged findings, updates `aidd/docs/tasklist/<ticket>.md`, runs `claude-workflow progress --source qa`, and feeds `gate-qa.sh`.

### Slash-command definitions
- Create branches with `git checkout -b feature/<TICKET>` (or other patterns from `config/conventions.json`).
- `aidd/commands/idea-new.md` — persists the ticket (and optional slug hint) in `aidd/docs/.active_ticket`/`.active_feature`, invokes `analyst` (research on demand), assembles the PRD, and captures outstanding questions **starting from an auto-generated `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`.**
- `aidd/commands/researcher.md` — prepares research context via `claude-workflow research`, gathers targets and updates `aidd/docs/research/<ticket>.md`.
- `aidd/commands/plan-new.md` — chains `planner` and `validator`, enforcing PRD `Status: READY` before plan creation.
- `aidd/commands/review-spec.md` — runs plan + PRD review via `plan-reviewer` → `prd-reviewer`, updates `## Plan Review` and `## PRD Review`, writes `reports/prd/<ticket>.json`, and exports blockers to the tasklist.
- `aidd/commands/tasks-new.md` — syncs `aidd/docs/tasklist/<ticket>.md` with the plan and migrates PRD Review action items with the proper slug hint/front matter.
- `aidd/commands/implement.md` — streamlines implementation steps, nudging to run tests and respect gates.
- `aidd/commands/review.md` — compiles review feedback, statuses, and checklist completion.
- `aidd/commands/qa.md` — runs the QA checks and stores `reports/qa/<ticket>.json`.
- Craft commits with `git commit`, aligning messages to the schemes described in `config/conventions.json`.

### Configuration & policy
- `.claude/settings.json` — `start/strict` presets, allow/ask/deny lists, and automation knobs (`format/tests`); hooks are supplied by the plugin.
- `config/conventions.json` — branch/commit modes (`ticket-prefix`, `conventional`, `mixed`), message templates, examples, and review/CLI guidance.
- `config/gates.json` — toggles for `prd_review`, `tests_required`, `deps_allowlist`, plus pointers to the active ticket/slug hint (`feature_ticket_source`, `feature_slug_hint_source`); drives gate behaviour and `lint-deps.sh`.
- `config/allowed-deps.txt` — comment-friendly `group:artifact` allowlist consumed by `lint-deps.sh`.

### Docs & templates
- **Runtime (LLM/agents)**: `aidd/AGENTS.md`, `aidd/docs/sdlc-flow.md`, `aidd/docs/status-machine.md`, `aidd/docs/prd/template.md`, `aidd/docs/plan/template.md`, `aidd/docs/tasklist/template.md`, `aidd/docs/research/template.md`, `aidd/docs/adr/template.md`.
- **Dev-only docs**: `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`, `doc/dev/feature-cookbook.md`, `doc/dev/prompt-playbook.md`, `doc/dev/prompt-versioning.md`, `doc/dev/release-notes.md`, `doc/dev/workflow.md`, `doc/dev/customization.md`.
- **Other templates**: `doc/dev/templates/prompts/prompt-agent.md`, `doc/dev/templates/prompts/prompt-command.md`, `doc/dev/templates/git-hooks/*.sample`, `doc/dev/templates/git-hooks/README.md`.

### Tests & quality
- `tests/helpers.py` — helper utilities to create files, initialise git, generate `config/gates.json`, and run hooks.
- `tests/test_init_claude_workflow.py` — validates bootstrap execution together with `--dry-run`, `--force`, and required artefacts.
- `tests/test_gate_*.py` — scenarios for workflow/API/DB/test gates, covering tracked/untracked migrations and mode toggles.
- `tests/test_format_and_test.py` — selective runner coverage with profiles, `moduleMatrix`, shared-file fallbacks, and env flags such as `SKIP_AUTO_TESTS`, `TEST_SCOPE`, `AIDD_TEST_*`.
- `tests/test_settings_policy.py` — ensures `permissions` stay safe and hooks are delegated to the plugin (not duplicated in settings).
- `tools/payload_audit.py` — audits payload contents against allowlist/denylist (guards against accidental dev-only files in the distro).

### Demos & extensions
- `examples/` — optional demo projects and scripts.
- `claude-workflow-extensions.patch` — patch file bundling agent, command, and gate extensions ready to apply to blank repositories.

## Architecture & relationships
- The bootstrap (`aidd/init-claude-workflow.sh`) generates `.claude/settings.json`, `.claude-plugin/marketplace.json`, and lays out the payload in `aidd/`; the `feature-dev-aidd` plugin attaches the hook pipeline.
- Pre/post hooks (`gate-*`, `format-and-test.sh`, `lint-deps.sh`) live in `aidd/hooks/hooks.json` and point to `${CLAUDE_PLUGIN_ROOT}/hooks/*` (core checks run on Stop/SubagentStop).
- Gate scripts (`gate-*`) consume `config/gates.json` and artefacts in `aidd/docs/**`, enforcing the `/idea-new → research (when needed) → /plan-new → /review-spec → /tasks-new` lifecycle; enable extra checks (`researcher`, `prd_review`, `tests_required`) as your process demands.
- Stages are tracked in `aidd/docs/.active_stage`: `format-and-test`, `gate-tests`, `lint-deps` run only during `implement`, `gate-qa` only during `qa`, and `gate-workflow` restricts code edits outside `implement/review/qa` when a stage is set.
- The Python test suite uses `tests/helpers.py` to emulate git/filesystem state, covering dry-run scenarios, tracked/untracked changes, and hook behaviour.

## Key scripts and hooks
- **`aidd/init-claude-workflow.sh`** — verifies `bash/git/python3`, generates `.claude/`, `.claude-plugin/`, and `aidd/**`, honours `--force`, prints dry-run plans, and persists the commit mode.
- **`aidd/hooks/format-and-test.sh`** — inspects `git diff`, resolves tasks via `automation.tests` (`changedOnly`, `moduleMatrix`, `fastTasks/fullTasks/targetedTask`), honours `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, `AIDD_TEST_*`, and escalates to full runs when shared files change; runs only in the `implement` stage.
- **`gate-workflow.sh`** — blocks edits under `src/**` until PRD, plan, Plan Review + PRD Review (via `/review-spec`), and new completed checkboxes (`- [x]` in `aidd/docs/tasklist/<ticket>.md`) exist for the active ticket (`aidd/docs/.active_ticket`).
- **`gate-prd-review.sh`** — calls `claude-workflow prd-review-gate`, which requires `aidd/docs/prd/<ticket>.prd.md`, a `## PRD Review` section with a status from `approved_statuses`, no open `- [ ]` action items, and a JSON report (`reports/prd/{ticket}.json` by default); blocking statuses, unchecked boxes, or report findings with severities from `blocking_severities` fail the gate, while `skip_branches`, `allow_missing_section`, `allow_missing_report`, and custom `report_path` values are controlled through `config/gates.json`.
- **`gate-tests.sh`** — optional gate: when enabled it expects matching tests as configured in `config/gates.json`, and ignores test folders via `exclude_dirs`.
- **`gate-qa.sh`** — runs `claude-workflow qa` (or the command from `config/gates.json`), writes `reports/qa/<ticket>.json`, and treats `blocker/critical` as hard failures; see `doc/dev/qa-playbook.md`.
- **`lint-deps.sh`** — enforces the dependency allowlist from `config/allowed-deps.txt` and highlights risky dependency manifest changes.
- **`scripts/ci-lint.sh`** — single entrypoint for `shellcheck`, `markdownlint`, `yamllint`, and `python -m unittest`, shared across local runs and GitHub Actions.
- **`scripts/smoke-workflow.sh`** — spins a temp project, invokes the init script, and validates the `/idea-new → research (when needed) → /plan-new → /review-spec → /tasks-new` gate sequence.
- **`examples/apply-demo.sh`** — applies the bootstrap to a demo project step by step, handy for workshops and demos.

## Test toolkit
- `tests/helpers.py` centralises helpers for file generation, git init/config, `config/gates.json` creation, and hook execution.
- `tests/test_init_claude_workflow.py` validates fresh installs, `--dry-run`, `--force`, and required artefacts emitted by the bootstrap.
- `tests/test_gate_*.py` cover workflow/API/DB/test gates, including tracked/untracked migration detection and `soft/hard/disabled` enforcement.
- `tests/test_format_and_test.py` exercises the Python hook, checking profiles, `moduleMatrix`, shared-file fallbacks, and env flags such as `SKIP_AUTO_TESTS`, `TEST_SCOPE`, and `AIDD_TEST_*`.
- `tests/test_settings_policy.py` guards `.claude/settings.json`, keeping critical commands (`git add/commit/push`, `curl`, prod writes) in `ask/deny` and asserting hooks stay delegated to the plugin.
- `scripts/ci-lint.sh` plus `.github/workflows/ci.yml` deliver linters and the unittest suite as a single local/CI entrypoint.
- `scripts/smoke-workflow.sh` runs an E2E smoke to ensure `gate-workflow` blocks code edits until Plan Review + PRD Review (run via `/review-spec`), the plan, and `aidd/docs/tasklist/<ticket>.md` artefacts exist.

## Access policies & gates
- `.claude/settings.json` contains `start` and `strict` presets: the former keeps minimal permissions, the latter expands allow/ask/deny; hooks come from the `feature-dev-aidd` plugin (`hooks/hooks.json`).
- The `automation` section drives formatting/test runners; adjust `format`/`tests` to match your stack.
- `config/gates.json` centralises `prd_review`, `tests_required`, `deps_allowlist`, and `qa` flags alongside ticket/slug-hint paths (`feature_ticket_source`, `feature_slug_hint_source`); the `prd_review` section exposes `approved_statuses`, `blocking_statuses`, `blocking_severities`, `allow_missing_section`, `allow_missing_report`, `report_path`, `skip_branches`, and `branches`.
- `aidd/docs/.active_stage` stores the current stage and scopes gate execution; override with `CLAUDE_SKIP_STAGE_CHECKS=1` or `CLAUDE_ACTIVE_STAGE` when needed.
- Combined `gate-*` hooks inside `aidd/hooks/` (invoked via the plugin) enforce the workflow: blocking code without plan/Plan Review/PRD Review/tasklist (`aidd/docs/tasklist/<ticket>.md`); run `/review-spec` for the review stages, require migrations/tests, and validate OpenAPI specs.

## Docs & templates
- **Runtime (LLM/agents)**: `aidd/AGENTS.md`, `aidd/docs/sdlc-flow.md`, `aidd/docs/status-machine.md`, `aidd/docs/prd/template.md`, `aidd/docs/plan/template.md`, `aidd/docs/tasklist/template.md`, `aidd/docs/research/template.md`, `aidd/docs/adr/template.md`.
- **Dev-only docs**: `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`, `doc/dev/feature-cookbook.md`, `doc/dev/prompt-playbook.md`, `doc/dev/prompt-versioning.md`, `doc/dev/release-notes.md`, `doc/dev/workflow.md`, `doc/dev/customization.md`.
- **Other templates**: `doc/dev/templates/prompts/prompt-agent.md`, `doc/dev/templates/prompts/prompt-command.md`, `doc/dev/templates/git-hooks/*.sample`, `doc/dev/templates/git-hooks/README.md`.
- Keep `README.md` and `README.en.md` in sync and update the _Last sync_ stamp whenever content changes.

## Examples & demos
- `examples/` contains optional demo projects (safe to delete if you do not need them).
- `examples/apply-demo.sh` applies the bootstrap to a demo workspace step by step, handy for workshops and demos.
- `scripts/smoke-workflow.sh` plus `doc/dev/workflow.md` provide a living example: the script automates the flow, the doc explains expected outcomes and troubleshooting tips.

## Installation

### Option A — `uv tool install` (recommended)

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci   # workspace → ./aidd
```

- `--target` always points to the workspace; the payload installs strictly under `./aidd`. Running CLI/hooks outside `aidd/` will fail with a clear “aidd/docs not found” message.
- the first command installs the `claude-workflow` CLI via `uv`;
- `claude-workflow init` mirrors the behaviour of `aidd/init-claude-workflow.sh`, copying hooks, docs, and templates into the current project;
- hooks invoke the installed `claude-workflow` binary directly, so ensure the CLI is on PATH (via `uv` or `pipx`);

### Option B — `pipx`

When `uv` is unavailable:

```bash
pipx install git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci   # workspace → ./aidd
```

`pipx` keeps the CLI isolated and upgradeable (`pipx upgrade claude-workflow-cli`).

### Option C — local script

1. Download or clone this repository and locate `src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh`.
2. Create the `aidd/` directory in your project.
3. Execute:

```bash
PAYLOAD_ROOT="/path/to/ai_driven_dev/src/claude_workflow_cli/data/payload/aidd"
mkdir -p aidd
(cd aidd && bash "${PAYLOAD_ROOT}/init-claude-workflow.sh" --commit-mode ticket-prefix --enable-ci)
# options:
#   --commit-mode ticket-prefix | conventional | mixed
#   --enable-ci   add CI workflow with manual trigger
#   --force       overwrite existing files
```

After bootstrap:

```bash
git add -A && git commit -m "chore: bootstrap Claude Code workflow"
```

## Prerequisites
- `bash`, `git`, `python3`;
- `uv` (https://github.com/astral-sh/uv) or `pipx` to install the CLI (optional but handy);
- build/test/formatting tools for your stack (optional).

Supports macOS/Linux. Use WSL or Git Bash on Windows.

## Quick start in Claude Code

```
git checkout -b feature/STORE-123
/idea-new STORE-123 checkout-discounts
claude-workflow research --ticket STORE-123 --auto --deep-code --call-graph
/plan-new checkout-discounts
/review-spec checkout-discounts
/tasks-new checkout-discounts
/implement checkout-discounts
/review checkout-discounts
/qa checkout-discounts
```

> The first argument is the ticket identifier; add an optional slug hint (e.g. `checkout-discounts`) as the second argument if you want a human-readable alias in `aidd/docs/.active_feature`.

You’ll get the essential artefacts (PRD, plan, plan review, PRD review, tasklist `aidd/docs/tasklist/<ticket>.md`): `/idea-new` immediately scaffolds `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`, the analyst records the dialog in `## Диалог analyst`, answers must follow the `Answer N:` pattern, and `aidd/hooks/format-and-test.sh` runs only during the `implement` stage on Stop/SubagentStop under gate control. Wrap up with `git commit` and `/review` to close the loop under the active convention.
Research defaults to workspace-relative paths (parent of `aidd/`); the CLI prints `base=workspace:/...` and hints to use `--paths-relative workspace` or pass absolute/`../` paths if the call graph or matches are empty.

## Feature kickoff checklist

1. Create/switch a branch (`git checkout -b feature/<TICKET>` or manually) and run `/idea-new <ticket> [slug-hint]` — it updates `aidd/docs/.active_ticket`, adds `.active_feature` when needed, **and scaffolds `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`.** It also records `aidd/docs/.active_stage=idea` (rerun the relevant command when requirements change). Answer every analyst prompt as `Answer N: …`; if context is thin, trigger research (`/researcher` or `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only]`), then return to the analyst until the dialog reaches `Status: READY` and `claude-workflow analyst-check --ticket <ticket>` reports success.
2. Generate discovery artifacts: `/idea-new`, research when needed (`claude-workflow research --ticket <ticket> --auto --deep-code --call-graph` + `/researcher`), `/plan-new`, `/review-spec`, `/tasks-new` until the status becomes READY (the ticket is already in place after step 1 and verified via `analyst-check`).
   > Call graph (via tree-sitter language pack) defaults to filter `<ticket>|<keywords>` and limit 300 edges in the context; the full graph is saved separately at `reports/research/<ticket>-call-graph-full.json`. Tune with `--graph-filter/--graph-limit/--graph-langs`.
3. Enable optional gates in `config/gates.json` when needed and prepare related artefacts (migrations, OpenAPI specs, extra tests).
4. Implement in small increments via `/implement`, watching messages from `gate-workflow` and any enabled gates. After every iteration tick the relevant tasklist items, update `Checkbox updated: …`, and run `claude-workflow progress --source implement --ticket <ticket>`.
5. Request `/review` once `aidd/docs/tasklist/<ticket>.md` checkboxes are complete, automated tests are green, and artefacts stay in sync — then re-run `claude-workflow progress --source review --ticket <ticket>` before closing the loop.
6. Before release, run `/qa <ticket>` or `claude-workflow qa --ticket <ticket> --report reports/qa/<ticket>.json --gate`, update the QA section in the tasklist, and confirm progress via `claude-workflow progress --source qa --ticket <ticket>`.
7. After QA/Review/Research reports, derive implementer tasks via `claude-workflow tasks-derive --source <qa|review|research> --append --ticket <ticket>` so new `- [ ]` link back to the reports in `aidd/docs/tasklist/<ticket>.md`; if needed, verify with `claude-workflow progress --source handoff --ticket <ticket>`.

A detailed agent/gate playbook lives in `doc/dev/agents-playbook.md`.

## Slash commands

Commands and agents ship as the `feature-dev-aidd` plugin in `aidd/.claude-plugin/` (manifest `plugin.json`); the files live in `aidd/commands` and `aidd/agents`, while workspace settings live under the root `.claude/`. Command frontmatter includes `description`, `argument-hint`, `allowed-tools`, `disable-model-invocation`, and positional `$1/$2/$ARGUMENTS`.

| Command | Purpose | Example |
| --- | --- | --- |
| `/idea-new` | Gather inputs and scaffold PRD (Status: draft → READY). Inputs: @aidd/docs/prd/template.md, @aidd/docs/research/<ticket>.md | `STORE-123 checkout-discounts` |
| `/researcher` | Use Researcher context to clarify scope and modules | `STORE-123` |
| `/plan-new` | Prepare plan and validation. Inputs: @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/research/<ticket>.md | `checkout-discounts` |
| `/review-spec` | Run review-plan + review-prd. Inputs: @aidd/docs/plan/<ticket>.md, @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/research/<ticket>.md | `checkout-discounts` |
| `/tasks-new` | Refresh `aidd/docs/tasklist/<ticket>.md` from the plan. Inputs: @aidd/docs/plan/<ticket>.md, @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/research/<ticket>.md | `checkout-discounts` |
| `/implement` | Execute the plan with auto tests. Inputs: @aidd/docs/plan/<ticket>.md, @aidd/docs/tasklist/<ticket>.md, @aidd/docs/prd/<ticket>.prd.md | `checkout-discounts` |
| `/review` | Final code review and status sync. Inputs: @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/plan/<ticket>.md, @aidd/docs/tasklist/<ticket>.md | `checkout-discounts` |
| `/qa` | Final QA gate, writes `reports/qa/<ticket>.json`. Inputs: @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/plan/<ticket>.md, @aidd/docs/tasklist/<ticket>.md | `checkout-discounts` |
| `claude-workflow progress` | Ensure new completed checkboxes exist before closing a step | `--source implement --ticket checkout-discounts` |

## Branch & commit modes

`config/conventions.json` ships with three presets:

- **ticket-prefix** (default): `feature/STORE-123` → `STORE-123: short summary`;
- **conventional**: `feat/orders` → `feat(orders): short summary`;
- **mixed**: `feature/STORE-123/feat/orders` → `STORE-123 feat(orders): short summary`.

Update `commit.mode` manually (`ticket-prefix`/`conventional`/`mixed`) and wire up a `commit-msg` hook from `doc/dev/customization.md` if you want automated validation.

## Selective tests

`aidd/hooks/format-and-test.sh`:
1. Reads `automation.tests` from `.claude/settings.json` (runner, `defaultTasks`, `fallbackTasks`, `moduleMatrix`).
2. Filters changed files (`git diff` + untracked) to relevant paths.
3. Maps paths via `moduleMatrix` to runner commands; falls back to `defaultTasks`/`fallbackTasks` when no match is found.
4. Runs in soft mode — export `STRICT_TESTS=1` to make failures blocking.
5. Auto-runs on Stop/SubagentStop only during the `implement` stage; export `SKIP_AUTO_TESTS=1` to pause the automated formatting/test run.

Troubleshooting tips and environment tweaks live in `doc/dev/workflow.md` and `doc/dev/customization.md`.

## Additional resources
- Step-by-step walkthrough with before/after structure: `examples/apply-demo.sh` and the "Stage overview" section in `doc/dev/workflow.md`.
- Workflow and gate overview: `doc/dev/workflow.md`.
- Agent & gate playbook: `doc/dev/agents-playbook.md`.
- Configuration deep dive: `doc/dev/customization.md`.
- Original Russian README: `README.md`.
- Demo scripts: `examples/`, `examples/apply-demo.sh`.
- Quick reference for slash commands: `aidd/commands/`.

## Migration to agent-first
1. **Update the repo and payload.** Pull the latest `main`, then run `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py` so the refreshed PRD/tasklist/research templates and `/idea-new` land both in the repo and in the CLI payload.
2. **Refresh `aidd/agents|commands` and prompt templates.** Copy the new prompts (or reinstall the workflow) to ensure all agents/commands list their repo-driven inputs and CLI tools; keep `doc/dev/templates/prompts/prompt-agent.md` / `prompt-command.md` in sync for future automation.
3. **Rehydrate active tickets.** For every ongoing feature run `claude-workflow research --ticket <ticket> --auto` (rebuilds `reports/research/*.json` + research docs) and `claude-workflow analyst-check --ticket <ticket>` to verify PRDs follow the new template. When needed, merge the “Automation/Commands” sections from the updated templates into existing artefacts manually.
4. **Validate gates/tests.** Execute `scripts/ci-lint.sh` and `scripts/smoke-workflow.sh` — they confirm tasklists now include `Reports/Commands`, prompts don’t rely on hardcoded `Answer N` strings, and payload parity holds.
5. **Document the change.** Add a short note to your team’s release notes / CHANGELOG so contributors know agents must log commands and cite repository data before escalating questions.

## CLI releases
- The package version comes from `pyproject.toml`; pushes to `main` trigger `.github/workflows/autotag.yml`, which creates `v<version>` tags when they do not exist yet.
- Tags matching `v*` run `release.yml`: the job builds `sdist`/`wheel` via `python -m build`, attaches them to the GitHub Release, and stores them as workflow artefacts.
- Users install the CLI directly from the repository, e.g. `uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git[@tag]` or `pipx install git+https://github.com/GrinRus/ai_driven_dev.git`.
- Update `CHANGELOG.md`/README before tagging, then validate `scripts/ci-lint.sh` and `claude-workflow smoke`. After the release, ensure GitHub Releases lists the artefacts and that installation instructions stay consistent.

## Contribution & license
- Follow `CONTRIBUTING.md` before opening PRs or issues.
- Licensed under MIT (`LICENSE`).
- Not affiliated with IDE/tool vendors — use at your own risk.
