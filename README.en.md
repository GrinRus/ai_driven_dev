# Claude Code Workflow — Java/Kotlin Monorepo Template

> Turn a plain Gradle repository into a Claude Code powered workspace with slash commands, safe hooks, and selective Gradle runs.

## Sync Guide
- Always edit `README.md` (RU) first, then update this translation in the same commit.
- Mirror section structure, headlines, and links. Leave a note if a Russian-only section has no equivalent.
- Update the date below whenever both files are aligned.

_Last sync with `README.md`: 2025-10-10._

## TL;DR
- `init-claude-workflow.sh` bootstraps the end-to-end flow `/idea-new → /plan-new → /tasks-new → /implement → /review` together with API/DB/test gates.
- Formatting and selective Gradle tests run automatically after each edit (set `SKIP_AUTO_TESTS=1` to disable temporarily), keeping the repo protected by `gate-*` hooks.
- Configurable branch/commit conventions via `config/conventions.json` plus ready-to-use docs and templates.
- Optional GitHub Actions, issue/PR templates, and Claude Code access policies.

## Table of Contents
- [What you get](#what-you-get)
- [Workflow architecture](#workflow-architecture)
- [Installation](#installation)
  - [Option A — curl](#option-a--curl)
  - [Option B — local file](#option-b--local-file)
- [Prerequisites](#prerequisites)
- [Quick start in Claude Code](#quick-start-in-claude-code)
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
/feature-new checkout-discounts STORE-123
/feature-adr checkout-discounts
/plan-new checkout-discounts
/tasks-new checkout-discounts
/api-spec-new checkout-discounts
/tests-generate checkout-discounts
/implement checkout-discounts
/review checkout-discounts
```

You’ll get the full artifact chain (PRD, plan, tasklist, OpenAPI, tests), automatic `/test-changed` runs guarded by gates, and `/commit` + `/review` workflows aligned with the active convention.

## Slash commands

| Command | Purpose | Example |
|---|---|---|
| `/branch-new` | Create/switch branch preset | `feature STORE-123` / `feat orders` / `mixed STORE-123 feat pricing` |
| `/feature-new` | Bootstrap PRD & starter assets | `checkout-discounts STORE-123` |
| `/feature-adr` | Generate ADR from PRD | `checkout-discounts` |
| `/plan-new` | Prepare plan and validation pass | `checkout-discounts` |
| `/tasks-new` | Refresh `tasklist.md` from the plan | `checkout-discounts` |
| `/implement` | Execute the plan with auto tests | `checkout-discounts` |
| `/review` | Final code review and status sync | `checkout-discounts` |
| `/api-spec-new` | Generate/update OpenAPI spec | `checkout-discounts` |
| `/tests-generate` | Produce unit/integration tests | `checkout-discounts` |
| `/docs-generate` | Generate/refresh docs | — |
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
- Configuration deep dive: `docs/customization.md`.
- Original Russian README: `README.md`.
- Sample Gradle monorepo & helper script: `examples/gradle-demo/`, `examples/apply-demo.sh`.
- Quick reference for slash commands: `.claude/commands/`.

## Contribution & license
- Follow `CONTRIBUTING.md` before opening PRs or issues.
- Licensed under MIT (`LICENSE`).
- Not affiliated with IDE/tool vendors — use at your own risk.
