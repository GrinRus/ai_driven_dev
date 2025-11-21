# Claude Code Workflow — Java/Kotlin Monorepo Template

> Turn a plain Gradle repository into a Claude Code powered workspace with slash commands, safe hooks, and selective Gradle runs.

## Sync Guide
- Always edit `README.md` (RU) first, then update this translation in the same commit.
- Mirror section structure, headlines, and links. Leave a note if a Russian-only section has no equivalent.
- Update the date below whenever both files are aligned.

_Last sync with `README.md`: 2025-11-19._

## TL;DR
- `init-claude-workflow.sh` bootstraps the end-to-end flow `/idea-new → claude-workflow research → /plan-new → /review-prd → /tasks-new → /implement → /review` with protective hooks and automated testing.
- Formatting and selective Gradle tests run automatically after each edit (set `SKIP_AUTO_TESTS=1` to disable temporarily), keeping the repo protected by `gate-*` hooks.
- Configurable branch/commit conventions via `config/conventions.json` plus ready-to-use docs and templates.
- Optional GitHub Actions, issue/PR templates, and Claude Code access policies.

## Table of Contents
- [What you get](#what-you-get)
- [Workflow architecture](#workflow-architecture)
- [Agent-first principles](#agent-first-principles)
- [Repository structure](#repository-structure)
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
- [Selective Gradle tests](#selective-gradle-tests)
- [Additional resources](#additional-resources)
- [Migration to agent-first](#migration-to-agent-first)
- [Contribution & license](#contribution--license)

## What you get
- Claude Code slash commands and sub-agents to bootstrap PRD/ADR/Tasklist docs, generate updates, and validate commits.
- A multi-stage workflow (idea → research → plan → PRD review → tasks → implementation → review → QA) powered by `analyst/researcher/planner/prd-reviewer/validator/implementer/reviewer/qa` sub-agents; additional gates are toggled via `config/gates.json`.
- Git hooks for auto-formatting, selective Gradle runs, and workflow guards.
- Commit convention presets (`ticket-prefix`, `conventional`, `mixed`) with documented templates for messages and branch names.
- Documentation pack, issue/PR templates, and optional CI workflow.
- Zero dependency on Spec Kit or BMAD — everything runs locally.

## Workflow architecture
1. `init-claude-workflow.sh` scaffolds `.claude/`, configs, and templates.
2. Slash commands drive the multi-stage process (see `workflow.md`): idea, plan, PRD review, tasklist, implementation, and review with dedicated sub-agents.
3. The `strict` preset in `.claude/settings.json` enables `gate-workflow`, `gate-prd-review`, and auto-runs `.claude/hooks/format-and-test.sh`; extra gates (`gate-api-contract`, `gate-db-migration`, `gate-tests`, `gate-qa`) are toggled via `config/gates.json`.
4. `.claude/hooks/format-and-test.sh` performs formatting and selective Gradle runs; full suites trigger automatically when shared assets change.
5. Policies and branch/commit presets are managed via `.claude/settings.json` and `config/conventions.json`.

## Agent-first principles
- **Slug-hint and repository first, questions later.** Analyst starts with the slug-hint stored in `docs/.active_feature`, then reads `docs/research/<ticket>.md`, `reports/research/*.json`, and existing plans before creating any Q&A. Researcher records every command (`claude-workflow research --auto`, `rg "<ticket>" src/**`, `find`, `python`), and implementer updates the tasklist plus lists executed `./gradlew` / `claude-workflow progress` runs before pinging the user.
- **Commands & logs are part of the answer.** Prompts and templates now require documenting allowed CLI invocations (Gradle, `rg`, `claude-workflow`) and attaching logs/paths so downstream agents can reproduce the steps. Tasklist and research templates include explicit `Commands/Reports` sections.
- **Auto-generated artifacts.** `/idea-new` scaffolds PRD, refreshes research reports, and instructs the analyst to mine repository data. The `templates/prompt-agent.md` / `templates/prompt-command.md` presets describe how to document inputs, gates, commands, and fail-fast rules in an agent-first style.

Advanced customization tips are covered in `workflow.md` and `docs/customization.md`.

## Repository structure
| Path | Purpose | Highlights |
| --- | --- | --- |
| `.claude/settings.json` | Access & automation policies | `start`/`strict` presets, pre/post hooks, auto formatting/tests |
| `.claude/commands/` | Slash-command definitions | Workflows for `/idea-new`, `/researcher`, `/plan-new`, `/review-prd`, `/tasks-new`, `/implement`, `/review` with `allowed-tools` and inline shell steps |
| `.claude/agents/` | Sub-agent playbooks | Roles for analyst, planner, prd-reviewer, validator, implementer, reviewer, qa, db-migrator, contract-checker |
| `.claude/hooks/` | Guard & utility hooks | `gate-workflow.sh`, `gate-prd-review.sh`, `gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh`, `gate-qa.sh`, `lint-deps.sh`, `format-and-test.sh` |
| `config/gates.json` | Gate toggles | Controls `api_contract`, `db_migration`, `prd_review`, `tests_required`, `deps_allowlist`, `qa`, `feature_ticket_source`, `feature_slug_hint_source` |
| `config/conventions.json` | Branch/commit presets | Detailed `ticket-prefix`, `conventional`, `mixed` templates plus branch patterns and review notes |
| `config/allowed-deps.txt` | Dependency allowlist | `group:artifact` entries inspected by `lint-deps.sh` |
| `docs/` | Guides & templates | `customization.md`, `agents-playbook.md`, `qa-playbook.md`, `feature-cookbook.md`, `release-notes.md`, PRD/ADR/tasklist templates and feature artefacts |
| `examples/` | Demo assets | `apply-demo.sh` and the placeholder Gradle monorepo `gradle-demo/` |
| `scripts/` | CLI helpers | `ci-lint.sh` (linters + tests), `smoke-workflow.sh` (E2E smoke for gate-workflow), `prd-review-agent.py` (heuristic PRD reviewer), `qa-agent.py` (heuristic QA agent) |
| `templates/` | Copyable templates | Git hooks (`commit-msg`, `pre-push`, `prepare-commit-msg`) and the extended `docs/tasklist/<ticket>.md` template |
| `tests/` | Python unit tests | Cover init bootstrap, hooks, selective tests, and settings policy |
| `.github/workflows/ci.yml` | CI pipeline | Installs linters and runs `scripts/ci-lint.sh` |
| `init-claude-workflow.sh` | Bootstrap script | Flags `--commit-mode`, `--enable-ci`, `--force`, `--dry-run`; dependency detection |
| `workflow.md` | Process playbook | Explains the idea → research → plan → PRD review → tasklist → implementation → review loop |

## Deep dive into components

### Bootstrap & utilities
- `init-claude-workflow.sh` — modular bootstrap with strict prerequisite checks (`bash/git/python3`, Gradle/ktlint), `--commit-mode/--enable-ci/--force/--dry-run`, generation of `.claude/`, `config/`, `docs/`, `templates/`, `.gitkeep`, and automatic commit-mode updates.
- `scripts/ci-lint.sh` — single entrypoint for `shellcheck`, `markdownlint`, `yamllint`, and `python -m unittest`; gracefully skips missing linters and is wired into CI.
- `scripts/smoke-workflow.sh` — E2E smoke scenario: spins a temp project, runs the bootstrap, walks the ticket-first loop (`ticket → PRD → plan → PRD review → tasklist`), and asserts `gate-workflow.sh`/`tasklist_progress` behaviour (changes without new `- [x]` are blocked).
- `examples/apply-demo.sh` — demonstrates applying the bootstrap to a Gradle monorepo, prints before/after trees, and runs `gradlew test` when the wrapper is available.
- The bootstrap provisions `.claude/hooks/*`, documentation, and the Gradle helper `.claude/gradle/init-print-projects.gradle`; branch and commit flows rely on native git commands guided by `config/conventions.json`.

### Hooks & automation
- `.claude/hooks/format-and-test.sh` — Python hook reading `.claude/settings.json`, honouring `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, inspecting `git diff` plus the active ticket/slug hint, switching between selective/full runs, and resolving tasks via `moduleMatrix`, `defaultTasks`, `fallbackTasks`.
- `.claude/hooks/gate-workflow.sh` — blocks edits under `src/**` until the active ticket has PRD, `## PRD Review` with `Status: approved`, plan, and fresh `- [x]` entries in `docs/tasklist/<ticket>.md` (the `tasklist_progress` gate), while ignoring documentation/template edits.
- `.claude/hooks/gate-prd-review.sh` — enforces PRD review readiness: inspects the active PRD, ensures the review section exists, and prevents merging when blockers remain.
- `.claude/hooks/gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh` — optional checks driven by `config/gates.json`, validating OpenAPI artefacts, Flyway/Liquibase migrations, and matching tests (`disabled|soft|hard`) with actionable hints.
- `.claude/hooks/lint-deps.sh` — monitors dependency changes, validates them against `config/allowed-deps.txt`, and reports drift.
- `.claude/gradle/init-print-projects.gradle` — helper Gradle script that registers `ccPrintProjectDirs` for selective runner module caching.

### Claude Code sub-agents
- `.claude/agents/analyst.md` — turns raw ideas into PRDs, asks clarifying questions, tracks risks/assumptions, and updates `docs/prd/<ticket>.prd.md` with READY/BLOCKED status.
- `.claude/agents/planner.md` — produces `docs/plan/<ticket>.md` with DoD and dependencies; `.claude/agents/validator.md` audits the plan and records follow-up questions for product/architecture.
- `.claude/agents/prd-reviewer.md` — performs structured PRD audits, verifies metrics/risks, fills `## PRD Review` (status, summary, findings, action items), and hands blockers back to product.
- `.claude/agents/implementer.md` — guides iterative delivery, tracks gate status, updates tasklists (`Checkbox updated: …`, new `- [x]`), and calls `claude-workflow progress --source implement` in between iterations.
- `.claude/agents/reviewer.md` — summarizes review findings, checks tasklists, flips READY/BLOCKED, records follow-up tasks in `docs/tasklist/<ticket>.md`, and runs `claude-workflow progress --source review` before handing off.
- `.claude/agents/db-migrator.md` — drafts Flyway/Liquibase migrations (`db/migration/V<timestamp>__<ticket>.sql`, changelog) and notes manual steps/dependencies.
- `.claude/agents/contract-checker.md` — compares controllers against OpenAPI specs, flags missing/extraneous endpoints/status codes, and provides actionable summaries.
- `.claude/agents/qa.md` — final QA sweep; produces severity-tagged findings, updates `docs/tasklist/<ticket>.md`, runs `claude-workflow progress --source qa`, and feeds `gate-qa.sh`.

### Slash-command definitions
- Create branches with `git checkout -b feature/<TICKET>` (or other patterns from `config/conventions.json`).
- `.claude/commands/idea-new.md` — persists the ticket (and optional slug hint) in `docs/.active_ticket`/`.active_feature`, invokes `analyst`, assembles the PRD, and captures outstanding questions **starting from an auto-generated `docs/prd/<ticket>.prd.md` with `Status: draft`.**
- `.claude/commands/researcher.md` — prepares research context via `claude-workflow research`, gathers targets and updates `docs/research/<ticket>.md`.
- `.claude/commands/plan-new.md` — chains `planner` and `validator`, enforcing a completed `## PRD Review` (`Status: approved`) before plan creation.
- `.claude/commands/review-prd.md` — calls `prd-reviewer`, writes the structured review block, stores `reports/prd/<ticket>.json`, and exports blockers to the tasklist.
- `.claude/commands/tasks-new.md` — syncs `docs/tasklist/<ticket>.md` with the plan and migrates PRD Review action items with the proper slug hint/front matter.
- `.claude/commands/implement.md` — streamlines implementation steps, nudging to run tests and respect gates.
- `.claude/commands/review.md` — compiles review feedback, statuses, and checklist completion.
- Craft commits with `git commit`, aligning messages to the schemes described in `config/conventions.json`.

### Configuration & policy
- `.claude/settings.json` — `start/strict` presets, allow/ask/deny lists, and automation knobs (`format/tests`).
- `config/conventions.json` — branch/commit modes (`ticket-prefix`, `conventional`, `mixed`), message templates, examples, and review/CLI guidance.
- `config/gates.json` — toggles for `prd_review`, `api_contract`, `db_migration`, `tests_required`, `deps_allowlist`, plus pointers to the active ticket/slug hint (`feature_ticket_source`, `feature_slug_hint_source`); drives gate behaviour and `lint-deps.sh`.
- `config/allowed-deps.txt` — comment-friendly `group:artifact` allowlist consumed by `lint-deps.sh`.

### Docs & templates
- `workflow.md`, `docs/customization.md`, `docs/agents-playbook.md` — cover the idea→research→PRD review→implementation lifecycle, bootstrap walkthrough, `.claude/settings.json` tuning, and sub-agent responsibilities.
- `docs/prd.template.md`, `docs/adr.template.md`, `docs/tasklist.template.md`, `templates/tasklist.md` — enriched artefact templates with prompts, checklists, and change logs.
- `templates/git-hooks/*.sample`, `templates/git-hooks/README.md` — ready-to-copy `commit-msg`, `prepare-commit-msg`, `pre-push` hooks with setup guidance and env toggles.
- `docs/release-notes.md` — release governance to steer the roadmap.

### Tests & quality
- `tests/helpers.py` — helper utilities to create files, initialise git, generate `config/gates.json`, and run hooks.
- `tests/test_init_claude_workflow.py` — validates bootstrap execution together with `--dry-run`, `--force`, and required artefacts.
- `tests/test_gate_*.py` — scenarios for workflow/API/DB/test gates, covering tracked/untracked migrations and mode toggles.
- `tests/test_format_and_test.py` — selective runner coverage with `moduleMatrix`, shared-file fallbacks, and env flags such as `SKIP_AUTO_TESTS`, `TEST_SCOPE`.
- `tests/test_settings_policy.py` — enforces `permissions`/`hooks` constraints in `.claude/settings.json`, ensuring critical commands stay in `ask/deny`.

### Demos & extensions
- `examples/gradle-demo/` — two-service Gradle monorepo (Kotlin 1.9.22, `jvmToolchain(17)`, JUnit 5) used to validate selective testing.
- `claude-workflow-extensions.patch` — patch file bundling agent, command, and gate extensions ready to apply to blank repositories.

## Architecture & relationships
- The bootstrap (`init-claude-workflow.sh`) generates `.claude/settings.json`, gates, and slash-command definitions that are invoked by the hook pipeline.
- The `strict` preset in `.claude/settings.json` wires pre/post hooks and automatically runs `.claude/hooks/format-and-test.sh` after successful writes.
- Gate scripts (`gate-*`) consume `config/gates.json` and artefacts in `docs/**`, enforcing the `/idea-new → claude-workflow research → /plan-new → /review-prd → /tasks-new` lifecycle; enable extra checks (`researcher`, `prd_review`, `api_contract`, `db_migration`, `tests_required`) as your process demands.
- `.claude/hooks/format-and-test.sh` relies on the Gradle helper `init-print-projects.gradle`, the active ticket/slug hint, and `moduleMatrix` to decide between selective and full test runs.
- The Python test suite uses `tests/helpers.py` to emulate git/filesystem state, covering dry-run scenarios, tracked/untracked changes, and hook behaviour.

## Key scripts and hooks
- **`init-claude-workflow.sh`** — verifies `bash/git/python3`, detects Gradle or kotlin linters, generates `.claude/ config/ docs/ templates/`, honours `--force`, prints dry-run plans, and persists the commit mode.
- **`.claude/hooks/format-and-test.sh`** — inspects `git diff`, resolves tasks via `automation.tests` (`changedOnly`, `moduleMatrix`), honours `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, and escalates to full runs when shared files change.
- **`gate-workflow.sh`** — blocks edits under `src/**` until PRD, PRD Review (`Status: approved`), plan, and new completed checkboxes (`- [x]` in `docs/tasklist/<ticket>.md`) exist for the active ticket (`docs/.active_ticket`).
- **`gate-prd-review.sh`** — funnels to `scripts/prd_review_gate.py`, which requires `docs/prd/<ticket>.prd.md`, a `## PRD Review` section with a status from `approved_statuses`, no open `- [ ]` action items, and a JSON report (`reports/prd/{ticket}.json` by default); blocking statuses, unchecked boxes, or report findings with severities from `blocking_severities` fail the gate, while `skip_branches`, `allow_missing_section`, `allow_missing_report`, and custom `report_path` values are controlled through `config/gates.json`.
- **`gate-api-contract.sh` / `gate-db-migration.sh` / `gate-tests.sh`** — optional gates: when enabled they expect OpenAPI specs, database migrations, and matching tests as configured in `config/gates.json`.
- **`gate-qa.sh`** — runs `scripts/qa-agent.py`, writes `reports/qa/<ticket>.json`, and treats `blocker/critical` as hard failures; see `docs/qa-playbook.md`.
- **`lint-deps.sh`** — enforces the dependency allowlist from `config/allowed-deps.txt` and highlights risky Gradle changes.
- **`scripts/ci-lint.sh`** — single entrypoint for `shellcheck`, `markdownlint`, `yamllint`, and `python -m unittest`, shared across local runs and GitHub Actions.
- **`scripts/smoke-workflow.sh`** — spins a temp project, invokes the init script, and validates the `/idea-new → claude-workflow research → /plan-new → /review-prd → /tasks-new` gate sequence.
- **`examples/apply-demo.sh`** — applies the bootstrap to a Gradle project step by step, handy for workshops and demos.

## Test toolkit
- `tests/helpers.py` centralises helpers for file generation, git init/config, `config/gates.json` creation, and hook execution.
- `tests/test_init_claude_workflow.py` validates fresh installs, `--dry-run`, `--force`, and required artefacts emitted by the bootstrap.
- `tests/test_gate_*.py` cover workflow/API/DB/test gates, including tracked/untracked migration detection and `soft/hard/disabled` enforcement.
- `tests/test_format_and_test.py` exercises the Python hook, checking `moduleMatrix`, shared-file fallbacks, and env flags such as `SKIP_AUTO_TESTS` and `TEST_SCOPE`.
- `tests/test_settings_policy.py` guards `.claude/settings.json`, ensuring critical commands (`git add/commit/push`, `curl`, prod writes) sit in `ask/deny`.
- `scripts/ci-lint.sh` plus `.github/workflows/ci.yml` deliver linters and the unittest suite as a single local/CI entrypoint.
- `scripts/smoke-workflow.sh` runs an E2E smoke to ensure `gate-workflow` blocks code edits until PRD Review, plan, and `docs/tasklist/<ticket>.md` artefacts exist.

## Access policies & gates
- `.claude/settings.json` contains `start` and `strict` presets: the former keeps minimal permissions, the latter enables pre/post hooks (`gate-*`, `format-and-test`, `lint-deps`) and requires approval for `git add/commit/push`.
- The `automation` section drives formatting/test runners; adjust `format`/`tests` there to align with your Gradle setup.
- `config/gates.json` centralises `prd_review`, `api_contract`, `db_migration`, `tests_required`, `deps_allowlist`, and `qa` flags alongside ticket/slug-hint paths (`feature_ticket_source`, `feature_slug_hint_source`); the `prd_review` section exposes `approved_statuses`, `blocking_statuses`, `blocking_severities`, `allow_missing_section`, `allow_missing_report`, `report_path`, `skip_branches`, and `branches`.
- Combined `gate-*` hooks inside `.claude/hooks/` enforce the workflow: blocking code without PRD review/plan/tasklist (`docs/tasklist/<ticket>.md`), requiring migrations/tests, and validating OpenAPI specs.

## Docs & templates
- `workflow.md` outlines the end-to-end idea → research → plan → tasks → implementation → review loop; `docs/agents-playbook.md` maps sub-agent responsibilities and deliverables.
- `workflow.md` also carries the Gradle bootstrap walkthrough, while `docs/customization.md` covers tuning `.claude/settings.json`, gates, and command templates.
- `docs/release-notes.md` tracks release cadence and the roadmap.
- PRD/ADR/tasklist templates (`docs/*.template.md`, `templates/tasklist.md`) plus git-hook samples (`templates/git-hooks/*.sample`) streamline onboarding.
- Keep `README.md` and `README.en.md` in sync and update the _Last sync_ stamp whenever content changes.

## Examples & demos
- `examples/gradle-demo/` ships a two-service monorepo (Kotlin 1.9.22, `jvmToolchain(17)`, JUnit 5) illustrating the target module layout for selective testing.
- `examples/apply-demo.sh` applies the bootstrap to a Gradle workspace step by step, handy for workshops and demos.
- `scripts/smoke-workflow.sh` plus `workflow.md` provide a living example: the script automates the flow, the doc explains expected outcomes and troubleshooting tips.

## Installation

### Option A — `uv tool install` (recommended)

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
```

- the first command installs the `claude-workflow` CLI via `uv`;
- `claude-workflow init` mirrors the behaviour of `init-claude-workflow.sh`, copying presets, hooks, and docs into the current project;
- the CLI now vendors the required Python modules into `.claude/hooks/_vendor`, so hooks that invoke `python3 -m claude_workflow_cli ...` run immediately with no extra `pip install`;
- need demo data? run `claude-workflow preset feature-prd --ticket demo-checkout`.

### Option B — `pipx`

When `uv` is unavailable:

```bash
pipx install git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
```

`pipx` keeps the CLI isolated and upgradeable (`pipx upgrade claude-workflow-cli`).

### Option C — local script

1. Download or clone this repository.
2. Place `init-claude-workflow.sh` next to your project.
3. Execute:

```bash
bash init-claude-workflow.sh --commit-mode ticket-prefix --enable-ci
# options:
#   --commit-mode ticket-prefix | conventional | mixed
#   --enable-ci   add CI workflow with manual trigger
#   --force       overwrite existing files
```

For public mirrors you can still rely on `curl`:

```bash
curl -fsSL https://raw.githubusercontent.com/GrinRus/ai_driven_dev/main/init-claude-workflow.sh \
  | bash -s -- --commit-mode ticket-prefix --enable-ci
```

After bootstrap:

```bash
git add -A && git commit -m "chore: bootstrap Claude Code workflow"
```

## Prerequisites
- `bash`, `git`, `python3`;
- `uv` (https://github.com/astral-sh/uv) or `pipx` to install the CLI (optional but handy);
- Gradle wrapper (`./gradlew`) or a local Gradle installation;
- optional: `ktlint` and/or Spotless.

Supports macOS/Linux. Use WSL or Git Bash on Windows.

## Quick start in Claude Code

```
git checkout -b feature/STORE-123
/idea-new STORE-123 checkout-discounts
/plan-new checkout-discounts
/review-prd checkout-discounts
/tasks-new checkout-discounts
/implement checkout-discounts
/review checkout-discounts
./.claude/hooks/format-and-test.sh
```

> The first argument is the ticket identifier; add an optional slug hint (e.g. `checkout-discounts`) as the second argument if you want a human-readable alias in `docs/.active_feature`.

You’ll get the essential artefacts (PRD, PRD review, plan, tasklist `docs/tasklist/<ticket>.md`): `/idea-new` immediately scaffolds `docs/prd/<ticket>.prd.md` with `Status: draft`, the analyst records the dialog in `## Диалог analyst`, answers must follow the `Answer N:` pattern, and `.claude/hooks/format-and-test.sh` runs guarded by gates. Wrap up with `git commit` and `/review` to close the loop under the active convention.

## Feature kickoff checklist

1. Create/switch a branch (`git checkout -b feature/<TICKET>` or manually) and run `/idea-new <ticket> [slug-hint]` — it updates `docs/.active_ticket`, adds `.active_feature` when needed, **and scaffolds `docs/prd/<ticket>.prd.md` with `Status: draft`.** Answer every analyst prompt as `Answer N: …`, update the PRD link to `docs/research/<ticket>.md`, and keep iterating until the dialog reaches `Status: READY` and `claude-workflow analyst-check --ticket <ticket>` reports success.
2. Generate discovery artifacts: `/idea-new`, `claude-workflow research --ticket <ticket>` + `/researcher`, `/plan-new`, `/review-prd`, `/tasks-new` until the status becomes READY/PASS (the ticket is already in place after step 1 and verified via `analyst-check`).
3. Enable optional gates in `config/gates.json` when needed and prepare related artefacts (migrations, OpenAPI specs, extra tests).
4. Implement in small increments via `/implement`, watching messages from `gate-workflow` and any enabled gates. After every iteration tick the relevant tasklist items, update `Checkbox updated: …`, and run `claude-workflow progress --source implement --ticket <ticket>`.
5. Request `/review` once `docs/tasklist/<ticket>.md` checkboxes are complete, automated tests are green, and artefacts stay in sync — then re-run `claude-workflow progress --source review|qa --ticket <ticket>` before closing the loop.

A detailed agent/gate playbook lives in `docs/agents-playbook.md`.

## Slash commands

| Command | Purpose | Example |
| --- | --- | --- |
| `/idea-new` | Gather inputs and scaffold PRD (Status: draft → READY) | `STORE-123 checkout-discounts` |
| `/plan-new` | Prepare plan and validation pass | `checkout-discounts` |
| `/review-prd` | Run structured PRD review and log status | `checkout-discounts` |
| `/tasks-new` | Refresh `docs/tasklist/<ticket>.md` from the plan | `checkout-discounts` |
| `/implement` | Execute the plan with auto tests | `checkout-discounts` |
| `/review` | Final code review and status sync | `checkout-discounts` |
| `claude-workflow progress` | Ensure new completed checkboxes exist before closing a step | `--source implement --ticket checkout-discounts` |

## Branch & commit modes

`config/conventions.json` ships with three presets:

- **ticket-prefix** (default): `feature/STORE-123` → `STORE-123: short summary`;
- **conventional**: `feat/orders` → `feat(orders): short summary`;
- **mixed**: `feature/STORE-123/feat/orders` → `STORE-123 feat(orders): short summary`.

Update `commit.mode` manually (`ticket-prefix`/`conventional`/`mixed`) and wire up a `commit-msg` hook from `docs/customization.md` if you want automated validation.

## Selective Gradle tests

`.claude/hooks/format-and-test.sh`:
1. Supports selective runs via `automation.tests.moduleMatrix`; generate module listings with `./gradlew -I .claude/gradle/init-print-projects.gradle ccPrintProjectDirs` and wire them into the matrix as needed.
2. Filters changed files (`git diff` + untracked) to build-impacting paths.
3. Maps them to Gradle modules, spawning tasks (`:module:clean :module:test`).
4. Falls back to `:jvmTest` / `:testDebugUnitTest` or repository-wide `gradle test`.
5. Runs in soft mode — export `STRICT_TESTS=1` to make failures blocking.
6. Auto-runs after writes (`/implement`, manual edits); export `SKIP_AUTO_TESTS=1` to pause the automated formatting/test run.

Troubleshooting tips and environment tweaks live in `workflow.md` and `docs/customization.md`.

## Additional resources
- Step-by-step walkthrough with before/after structure: `examples/apply-demo.sh` and the "Stage overview" section in `workflow.md`.
- Workflow and gate overview: `workflow.md`.
- Agent & gate playbook: `docs/agents-playbook.md`.
- Configuration deep dive: `docs/customization.md`.
- Original Russian README: `README.md`.
- Sample Gradle monorepo & helper script: `examples/gradle-demo/`, `examples/apply-demo.sh`.
- Quick reference for slash commands: `.claude/commands/`.

## Migration to agent-first
1. **Update the repo and payload.** Pull the latest `main`, then run `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py` so the refreshed PRD/tasklist/research templates and `/idea-new` land both in the repo and in the CLI payload.
2. **Refresh `.claude/agents|commands` and prompt templates.** Copy the new RU/EN prompts (or reinstall the workflow) to ensure all agents/commands list their repo-driven inputs and CLI tools; keep `templates/prompt-agent.md` / `prompt-command.md` in sync for future automation.
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
