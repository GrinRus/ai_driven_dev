# Claude Code Workflow — Java/Kotlin Monorepo Template

> Turn a plain Gradle repository into a Claude Code powered workspace with slash commands, safe hooks, and selective Gradle runs.

## Sync Guide
- Always edit `README.md` (RU) first, then update this translation in the same commit.
- Mirror section structure, headlines, and links. Leave a note if a Russian-only section has no equivalent.
- Update the date below whenever both files are aligned.

_Last sync with `README.md`: 2025-10-12._

## TL;DR
- `init-claude-workflow.sh` bootstraps the end-to-end flow `/idea-new → /plan-new → /tasks-new → /implement → /review` together with API/DB/test gates.
- Formatting and selective Gradle tests run automatically after each edit (set `SKIP_AUTO_TESTS=1` to disable temporarily), keeping the repo protected by `gate-*` hooks.
- Configurable branch/commit conventions via `config/conventions.json` plus ready-to-use docs and templates.
- Optional GitHub Actions, issue/PR templates, and Claude Code access policies.

## Table of Contents
- [What you get](#what-you-get)
- [Workflow architecture](#workflow-architecture)
- [Repository structure](#repository-structure)
- [Deep dive into components](#deep-dive-into-components)
- [Architecture & relationships](#architecture--relationships)
- [Key scripts and hooks](#key-scripts-and-hooks)
- [Test toolkit](#test-toolkit)
- [Access policies & gates](#access-policies--gates)
- [Docs & templates](#docs--templates)
- [Examples & demos](#examples--demos)
- [Installation](#installation)
  - [Option A — curl](#option-a--curl)
  - [Option B — local file](#option-b--local-file)
- [Prerequisites](#prerequisites)
- [Quick start in Claude Code](#quick-start-in-claude-code)
- [Feature kickoff checklist](#feature-kickoff-checklist)
- [Slash commands](#slash-commands)
- [Branch & commit modes](#branch--commit-modes)
- [Selective Gradle tests](#selective-gradle-tests)
- [Additional resources](#additional-resources)
- [Contribution & license](#contribution--license)

## What you get
- Claude Code slash commands and sub-agents to bootstrap PRD/ADR/Tasklist docs, generate updates, and validate commits.
- A multi-stage workflow (idea → plan → validation → tasks → implementation → review) powered by `analyst/planner/validator/implementer/reviewer` sub-agents plus `/api-spec-new` and `/tests-generate`.
- Git hooks for auto-formatting, selective Gradle runs, and protection of production artifacts.
- Commit convention presets (`ticket-prefix`, `conventional`, `mixed`) with CLI helpers.
- Documentation pack, issue/PR templates, and optional CI workflow.
- Zero dependency on Spec Kit or BMAD — everything runs locally.

## Workflow architecture
1. `init-claude-workflow.sh` scaffolds `.claude/`, configs, and templates.
2. Slash commands drive the multi-stage process (see `workflow.md`): idea, plan, validation, tasklist, implementation, and review with dedicated sub-agents.
3. The `strict` preset in `.claude/settings.json` enables `gate-workflow`, `gate-api-contract`, `gate-db-migration`, `gate-tests`, and auto-runs `/test-changed` after each write.
4. `.claude/hooks/format-and-test.sh` performs formatting and selective Gradle runs; full suites trigger automatically when shared assets change.
5. Policies and branch/commit presets are managed via `.claude/settings.json` and `config/conventions.json`.

Advanced customization tips are covered in `workflow.md` and `docs/customization.md`.

## Repository structure
| Path | Purpose | Highlights |
| --- | --- | --- |
| `.claude/settings.json` | Access & automation policies | `start`/`strict` presets, pre/post hooks, auto formatting/tests, production path protection |
| `.claude/commands/` | Slash-command definitions | Workflows for `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review` with `allowed-tools` and inline shell steps |
| `.claude/agents/` | Sub-agent playbooks | Roles for analyst, planner, validator, implementer, reviewer, api-designer, qa-author, db-migrator, contract-checker |
| `.claude/hooks/` | Guard & utility hooks | `gate-workflow.sh`, `gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh`, `protect-prod.sh`, `lint-deps.sh`, `format-and-test.sh` |
| `config/gates.json` | Gate toggles | Controls `api_contract`, `db_migration`, `tests_required`, `deps_allowlist`, and `feature_slug_source` |
| `config/conventions.json` | Branch/commit presets | Detailed `ticket-prefix`, `conventional`, `mixed` templates plus branch patterns and review notes |
| `config/allowed-deps.txt` | Dependency allowlist | `group:artifact` entries inspected by `lint-deps.sh` |
| `doc/backlog.md` | Wave backlog | Tracks Wave 1/2 tasks and completion status |
| `docs/` | Guides & templates | `usage-demo.md`, `customization.md`, `agents-playbook.md`, `release-notes.md`, PRD/ADR/tasklist templates and feature artefacts |
| `examples/` | Demo assets | `apply-demo.sh` and the placeholder Gradle monorepo `gradle-demo/` |
| `scripts/` | CLI helpers | `ci-lint.sh` (linters + tests) and `smoke-workflow.sh` (E2E smoke for gate-workflow) |
| `templates/` | Copyable templates | Git hooks (`commit-msg`, `pre-push`, `prepare-commit-msg`) and the extended `tasklist.md` |
| `tests/` | Python unit tests | Cover init bootstrap, hooks, selective tests, and settings policy |
| `.github/workflows/ci.yml` | CI pipeline | Installs linters and runs `scripts/ci-lint.sh` |
| `init-claude-workflow.sh` | Bootstrap script | Flags `--commit-mode`, `--enable-ci`, `--force`, `--dry-run`; dependency detection |
| `workflow.md` | Process playbook | Explains the idea → plan → tasks → implement → review loop |

## Deep dive into components

### Bootstrap & utilities
- `init-claude-workflow.sh` — modular bootstrap with strict prerequisite checks (`bash/git/python3`, Gradle/ktlint), `--commit-mode/--enable-ci/--force/--dry-run`, generation of `.claude/`, `config/`, `docs/`, `templates/`, `.gitkeep`, CLI helpers, and automatic commit-mode updates.
- `scripts/ci-lint.sh` — single entrypoint for `shellcheck`, `markdownlint`, `yamllint`, and `python -m unittest`; gracefully skips missing linters and is wired into CI.
- `scripts/smoke-workflow.sh` — E2E smoke scenario: spins a temp project, runs the bootstrap, walks slug → PRD → plan → tasklist, and asserts `gate-workflow.sh` behaviour.
- `examples/apply-demo.sh` — demonstrates applying the bootstrap to a Gradle monorepo, prints before/after trees, and runs `gradlew test` when the wrapper is available.
- CLI generated by the bootstrap (`scripts/commit_msg.py`, `scripts/branch_new.py`, `scripts/conventions_set.py`) — build commit messages, create branches per presets, and switch commit modes on demand; the helpers live in the repository and are refreshed during reinstall.

### Hooks & automation
- `.claude/hooks/format-and-test.sh` — Python hook reading `.claude/settings.json`, honouring `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, inspecting `git diff` plus the active slug, switching between selective/full runs, and resolving tasks via `moduleMatrix`, `defaultTasks`, `fallbackTasks`.
- `.claude/hooks/gate-workflow.sh` — blocks edits under `src/**` until the active slug has PRD, plan, and tasklist checkboxes, while ignoring documentation/template edits.
- `.claude/hooks/gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh` — gates from `config/gates.json` ensuring OpenAPI artefacts (yaml/json), Flyway/Liquibase migrations (tracked and untracked), and matching tests for `soft/hard/disabled` modes with actionable hints.
- `.claude/hooks/protect-prod.sh` and `lint-deps.sh` — guard production paths (`infra/prod/**`, `deploy/prod/**`), honour `PROTECT_PROD_BYPASS`/`PROTECT_LOG_ONLY`, and flag Gradle dependencies outside `config/allowed-deps.txt`.
- `.claude/gradle/init-print-projects.gradle` — helper Gradle script that registers `ccPrintProjectDirs` for selective runner module caching.

### Claude Code sub-agents
- `.claude/agents/analyst.md` — turns raw ideas into PRDs, asks clarifying questions, tracks risks/assumptions, and updates `docs/prd/<slug>.prd.md` with READY/BLOCKED status.
- `.claude/agents/planner.md` — produces `docs/plan/<slug>.md` with DoD and dependencies; `.claude/agents/validator.md` audits the plan and records follow-up questions for product/architecture.
- `.claude/agents/implementer.md` — guides iterative delivery, enforces `/test-changed`, tracks gate status, and keeps `tasklist.md` aligned.
- `.claude/agents/reviewer.md` — summarizes review findings, checks tasklists, flips READY/BLOCKED, and records follow-up tasks.
- `.claude/agents/api-designer.md` — prepares/updates `docs/api/<slug>.yaml`, describing CRUD/edge cases, error schema, and outstanding questions.
- `.claude/agents/qa-author.md` — generates unit/integration tests, `docs/test/<slug>-manual.md`, triggers `/test-changed`, and reports coverage.
- `.claude/agents/db-migrator.md` — drafts Flyway/Liquibase migrations (`db/migration/V<timestamp>__<slug>.sql`, changelog) and notes manual steps/dependencies.
- `.claude/agents/contract-checker.md` — compares controllers against OpenAPI specs, flags missing/extraneous endpoints/status codes, and provides actionable summaries.

### Slash-command definitions
- `.claude/commands/feature-activate.md` — locks the active slug in `docs/.active_feature`, activating gate enforcement.
- `.claude/commands/branch-new.md` — calls `scripts/branch_new.py` to create branches (`feature/`, `feat/`, `hotfix/`, `mixed`) and returns the final name.
- `.claude/commands/idea-new.md` — invokes `analyst` to assemble the PRD, capture outstanding questions, and persist the slug.
- `.claude/commands/plan-new.md` — chains `planner` and `validator`, updating the plan and validation outcomes.
- `.claude/commands/tasks-new.md` — syncs `tasklist.md` with the plan, grouping items by stage and slug.
- `.claude/commands/api-spec-new.md` — delegates OpenAPI authoring to `api-designer`, flagging remaining questions.
- `.claude/commands/tests-generate.md` — calls `qa-author` for automated tests and manual scenarios.
- `.claude/commands/implement.md` — streamlines implementation steps, nudging to run tests and respect gates.
- `.claude/commands/review.md` — compiles review feedback, statuses, and checklist completion.
- `.claude/commands/commit.md` & `commit-validate.md` — rely on `scripts/commit_msg.py` to assemble/validate messages per `config/conventions.json`.
- `.claude/commands/test-changed.md` — wraps `format-and-test.sh` for selective Gradle execution with custom scopes.

### Configuration & policy
- `.claude/settings.json` — `start/strict` presets, allow/ask/deny lists, pre/post hooks, automation knobs (`format/tests`), and production protection with `PROTECT_PROD_BYPASS`/`PROTECT_LOG_ONLY`.
- `config/conventions.json` — branch/commit modes (`ticket-prefix`, `conventional`, `mixed`), message templates, examples, and review/CLI guidance.
- `config/gates.json` — toggles for `api_contract`, `db_migration`, `tests_required`, `deps_allowlist`, and `feature_slug_source`; drives gate behaviour and `lint-deps.sh`.
- `config/allowed-deps.txt` — comment-friendly `group:artifact` allowlist consumed by `lint-deps.sh`.

### Docs & templates
- `workflow.md`, `docs/customization.md`, `docs/usage-demo.md`, `docs/agents-playbook.md` — cover the idea→review process, bootstrap walkthrough, `.claude/settings.json` tuning, and sub-agent responsibilities.
- `docs/prd.template.md`, `docs/adr.template.md`, `docs/tasklist.template.md`, `templates/tasklist.md` — enriched artefact templates with prompts, checklists, and change logs.
- `templates/git-hooks/*.sample`, `templates/git-hooks/README.md` — ready-to-copy `commit-msg`, `prepare-commit-msg`, `pre-push` hooks with setup guidance and env toggles.
- `doc/backlog.md`, `docs/release-notes.md` — wave backlog (Wave 1/2) and release governance to steer the roadmap.

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
- The bootstrap (`init-claude-workflow.sh`) generates `.claude/settings.json`, gates, and CLI helpers that are invoked by slash commands and hook pipelines.
- The `strict` preset in `.claude/settings.json` wires pre/post hooks, automatically runs `.claude/hooks/format-and-test.sh` after successful writes, and guards production paths.
- Gate scripts (`gate-*`) consume `config/gates.json` and artefacts in `docs/**`, enforcing the `/idea-new → /plan-new → /tasks-new` lifecycle; `/api-spec-new` and `/tests-generate` trigger sub-agents to unblock code changes.
- `.claude/hooks/format-and-test.sh` relies on the Gradle helper `init-print-projects.gradle`, the active slug, and `moduleMatrix` to decide between selective and full test runs.
- The Python test suite uses `tests/helpers.py` to emulate git/filesystem state, covering dry-run scenarios, tracked/untracked changes, and hook behaviour.

## Key scripts and hooks
- **`init-claude-workflow.sh`** — verifies `bash/git/python3`, detects Gradle or kotlin linters, generates `.claude/ config/ docs/ templates/`, honours `--force`, prints dry-run plans, and persists the commit mode.
- **`.claude/hooks/format-and-test.sh`** — inspects `git diff`, resolves tasks via `automation.tests` (`changedOnly`, `moduleMatrix`), honours `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, and escalates to full runs when shared files change.
- **`gate-workflow.sh`** — blocks edits under `src/**` until PRD, plan, and tasklist entries exist for the active slug (`docs/.active_feature`), checking for tasklist checkboxes.
- **`gate-api-contract.sh` / `gate-db-migration.sh` / `gate-tests.sh`** — request OpenAPI specs, database migrations, and matching tests according to `config/gates.json` (`soft/hard/disabled`).
- **`protect-prod.sh` & `lint-deps.sh`** — guard production paths (`infra/prod/**`, `deploy/prod/**`), enforce dependency allowlists, and respect `PROTECT_PROD_BYPASS` / `PROTECT_LOG_ONLY`.
- **`scripts/ci-lint.sh`** — single entrypoint for `shellcheck`, `markdownlint`, `yamllint`, and `python -m unittest`, shared across local runs and GitHub Actions.
- **`scripts/smoke-workflow.sh`** — spins a temp project, invokes the init script, and validates the `/idea-new → /plan-new → /tasks-new` gate sequence.
- **`examples/apply-demo.sh`** — applies the bootstrap to a Gradle project step by step, handy for workshops and demos.

## Test toolkit
- `tests/helpers.py` centralises helpers for file generation, git init/config, `config/gates.json` creation, and hook execution.
- `tests/test_init_claude_workflow.py` validates fresh installs, `--dry-run`, `--force`, and required artefacts emitted by the bootstrap.
- `tests/test_gate_*.py` cover workflow/API/DB/test gates, including tracked/untracked migration detection and `soft/hard/disabled` enforcement.
- `tests/test_format_and_test.py` exercises the Python hook, checking `moduleMatrix`, shared-file fallbacks, and env flags such as `SKIP_AUTO_TESTS` and `TEST_SCOPE`.
- `tests/test_settings_policy.py` guards `.claude/settings.json`, ensuring critical commands (`git add/commit/push`, `curl`, prod writes) sit in `ask/deny`.
- `scripts/ci-lint.sh` plus `.github/workflows/ci.yml` deliver linters and the unittest suite as a single local/CI entrypoint.
- `scripts/smoke-workflow.sh` runs an E2E smoke to ensure `gate-workflow` blocks code edits until artefacts exist.

## Access policies & gates
- `.claude/settings.json` contains `start` and `strict` presets: the former keeps minimal permissions, the latter enables pre/post hooks (`protect-prod`, `gate-*`, `format-and-test`, `lint-deps`) and requires approval for `git add/commit/push`.
- The `automation` section drives formatting/test runners, while `protection` secures production paths with `PROTECT_PROD_BYPASS` and `PROTECT_LOG_ONLY` environment switches.
- `config/gates.json` centralises `api_contract`, `db_migration`, `tests_required`, and `deps_allowlist` flags alongside the active slug path (`feature_slug_source`).
- Combined `gate-*` hooks inside `.claude/hooks/` enforce the workflow: blocking code without PRD/plan/tasklist, requiring migrations/tests, and validating OpenAPI specs.

## Docs & templates
- `workflow.md` outlines the end-to-end idea → plan → tasks → implementation → review loop; `docs/agents-playbook.md` maps sub-agent responsibilities and deliverables.
- `docs/usage-demo.md` provides a Gradle bootstrap walkthrough, while `docs/customization.md` covers tuning `.claude/settings.json`, gates, and command templates.
- `docs/release-notes.md` and `doc/backlog.md` track release cadence and the Wave 1/2 roadmap.
- PRD/ADR/tasklist templates (`docs/*.template.md`, `templates/tasklist.md`) plus git-hook samples (`templates/git-hooks/*.sample`) streamline onboarding.
- Keep `README.md` and `README.en.md` in sync and update the _Last sync_ stamp whenever content changes.

## Examples & demos
- `examples/gradle-demo/` ships a two-service monorepo (Kotlin 1.9.22, `jvmToolchain(17)`, JUnit 5) illustrating the target module layout for selective testing.
- `examples/apply-demo.sh` applies the bootstrap to a Gradle workspace step by step, handy for workshops and demos.
- `scripts/smoke-workflow.sh` plus `docs/usage-demo.md` provide a living example: the script automates the flow, the doc explains expected outcomes and troubleshooting tips.

## Installation

### Option A — curl

> Replace `<your-org>/<repo>` with the repository that stores `init-claude-workflow.sh`.

```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/<repo>/main/init-claude-workflow.sh \
  | bash -s -- --commit-mode ticket-prefix --enable-ci
```

### Option B — local file

1. Copy `init-claude-workflow.sh` into the project root.
2. Run:

```bash
bash init-claude-workflow.sh --commit-mode ticket-prefix --enable-ci
# options:
#   --commit-mode ticket-prefix | conventional | mixed
#   --enable-ci   add CI workflow with manual trigger
#   --force       overwrite existing files
```

Finish with:

```bash
git add -A && git commit -m "chore: bootstrap Claude Code workflow"
```

## Prerequisites
- `bash`, `git`, `python3`;
- Gradle wrapper (`./gradlew`) or a local Gradle installation;
- optional: `ktlint` and/or Spotless.

Supports macOS/Linux. Use WSL or Git Bash on Windows.

## Quick start in Claude Code

```
/branch-new feature STORE-123
/feature-activate checkout-discounts
/idea-new checkout-discounts STORE-123
/plan-new checkout-discounts
/tasks-new checkout-discounts
/api-spec-new checkout-discounts
/tests-generate checkout-discounts
/implement checkout-discounts
/review checkout-discounts
```

You’ll get the full artifact chain (PRD, plan, tasklist, OpenAPI, tests), automatic `/test-changed` runs guarded by gates, and `/commit` + `/review` workflows aligned with the active convention.

## Feature kickoff checklist

1. Create/switch a branch via `/branch-new` (or manually) and activate the slug with `/feature-activate <slug>`.
2. Generate discovery artifacts: `/idea-new`, `/plan-new`, `/tasks-new` until the status becomes READY/PASS.
3. Prepare integrations and data: `/api-spec-new`, run `contract-checker`, and call `db-migrator` when the domain model changes.
4. Close the testing loop: `/tests-generate`, make sure `gate-tests` no longer warns or blocks edits.
5. Implement in small increments via `/implement`, watching messages from `gate-workflow`, `gate-api-contract`, and `gate-db-migration`.
6. Request `/review` once `tasklist.md` checkboxes are complete, tests are green, and artifacts stay in sync.

A detailed agent/gate playbook lives in `docs/agents-playbook.md`.

## Slash commands

| Command | Purpose | Example |
|---|---|---|
| `/branch-new` | Create/switch branch preset | `feature STORE-123` / `feat orders` / `mixed STORE-123 feat pricing` |
| `/feature-activate` | Lock the active feature slug | `checkout-discounts` |
| `/idea-new` | Gather inputs and draft a PRD | `checkout-discounts STORE-123` |
| `/plan-new` | Prepare plan and validation pass | `checkout-discounts` |
| `/tasks-new` | Refresh `tasklist.md` from the plan | `checkout-discounts` |
| `/implement` | Execute the plan with auto tests | `checkout-discounts` |
| `/review` | Final code review and status sync | `checkout-discounts` |
| `/api-spec-new` | Generate/update OpenAPI spec | `checkout-discounts` |
| `/tests-generate` | Produce unit/integration tests | `checkout-discounts` |
| `/test-changed` | Run selective Gradle tests | — |
| `/conventions-set` | Switch commit mode | `conventional` / `ticket-prefix` / `mixed` |
| `/conventions-sync` | Sync `conventions.md` with Gradle configs | — |
| `/commit` | Craft & run a commit | `"implement rule engine"` |
| `/commit-validate` | Validate a commit message | `"feat(orders): add x"` |

## Branch & commit modes

`config/conventions.json` ships with three presets:

- **ticket-prefix** (default): `feature/STORE-123` → `STORE-123: short summary`;
- **conventional**: `feat/orders` → `feat(orders): short summary`;
- **mixed**: `feature/STORE-123/feat/orders` → `STORE-123 feat(orders): short summary`.

Switch via `/conventions-set conventional` or the CLI helper. Add a commit-msg hook from `docs/customization.md` to enforce the rules locally.

## Selective Gradle tests

`.claude/hooks/format-and-test.sh`:
1. Builds a project map via `.claude/gradle/init-print-projects.gradle`.
2. Filters changed files (`git diff` + untracked) to build-impacting paths.
3. Maps them to Gradle modules, spawning tasks (`:module:clean :module:test`).
4. Falls back to `:jvmTest` / `:testDebugUnitTest` or repository-wide `gradle test`.
5. Runs in soft mode — export `STRICT_TESTS=1` to make failures blocking.
6. Auto-runs after writes (`/implement`, manual edits); export `SKIP_AUTO_TESTS=1` to pause automatic `/test-changed` executions.

Troubleshooting tips and environment tweaks live in `docs/usage-demo.md` and `docs/customization.md`.

## Additional resources
- Step-by-step walkthrough with before/after structure: `docs/usage-demo.md`.
- Workflow and gate overview: `workflow.md`.
- Agent & gate playbook: `docs/agents-playbook.md`.
- Configuration deep dive: `docs/customization.md`.
- Original Russian README: `README.md`.
- Sample Gradle monorepo & helper script: `examples/gradle-demo/`, `examples/apply-demo.sh`.
- Quick reference for slash commands: `.claude/commands/`.

## Contribution & license
- Follow `CONTRIBUTING.md` before opening PRs or issues.
- Licensed under MIT (`LICENSE`).
- Not affiliated with IDE/tool vendors — use at your own risk.
