# AIDD Claude Code Plugin - Language-agnostic Workflow Template

> A ready-to-use Claude Code plugin: slash commands, agents, hooks, and templates for the idea -> research -> plan -> review-spec -> spec-interview (optional) -> tasklist -> implement -> review -> qa flow.

_Last sync with `README.md`: 2026-02-25._

## Table of Contents
- [What it is](#what-it-is)
- [Get Started](#get-started)
- [Scripts and Checks](#scripts-and-checks)
- [Slash Commands](#slash-commands)
- [Documentation](#documentation)
- [Prerequisites](#prerequisites)
- [Contributing](#contributing)
- [License](#license)

## What it is
AIDD (AI-Driven Development) organizes LLM work as an artifact- and gate-driven workflow instead of ad-hoc responses.

At a glance:
- `aidd/docs/**` and `aidd/reports/**` are the working artifact surface;
- public stage flow: `idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa`;
- canonical runtime entrypoints: `skills/*/runtime/*.py`;
- hook entrypoints are migrated to `hooks/*.py`;
- repository quality is enforced by guards and smoke/e2e scenarios.

For breaking path and entrypoint changes, see:
- [docs/runbooks/prod-like-breaking-migration.md](docs/runbooks/prod-like-breaking-migration.md)

## Get Started

### 1) Install the plugin
```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

### 2) Initialize the workspace
```text
/feature-dev-aidd:aidd-init
```

### 3) Run the feature flow
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
- `spec-interview` is optional.
- `/feature-dev-aidd:aidd-init` without `--force` keeps existing files.
- The user runtime guide is generated in workspace as `aidd/AGENTS.md`.

## Scripts and Checks

| Command | Purpose |
| --- | --- |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py` | Initialize `./aidd` from templates |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py` | Environment and path diagnostics |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket>` | Build RLM research artifacts |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py --source <stage> --ticket <ticket>` | Validate tasklist progress |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket>` | Single loop step (fresh session) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --max-iterations 5` | Auto-loop implement/review |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py --ticket <ticket> --gate` | QA report + gate |
| `tests/repo_tools/ci-lint.sh` | Repo linters + unit/integration tests |
| `tests/repo_tools/smoke-workflow.sh` | Repo E2E smoke workflow |
| `python3 tests/repo_tools/dist_manifest_check.py --root .` | Validate distribution content |

For full maintainer checks, guards, and ownership map, see [AGENTS.md](AGENTS.md).

## Slash Commands

| Command | Purpose | Arguments |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Initialize workspace | `[--force] [--detect-build-tools]` |
| `/feature-dev-aidd:idea-new` | PRD draft + questions | `<TICKET> [note...]` |
| `/feature-dev-aidd:researcher` | Research stage | `<TICKET> [note...] [--paths ... --keywords ...]` |
| `/feature-dev-aidd:plan-new` | Plan and validation | `<TICKET> [note...]` |
| `/feature-dev-aidd:review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/feature-dev-aidd:spec-interview` | Optional clarifications | `<TICKET> [note...]` |
| `/feature-dev-aidd:tasks-new` | Build tasklist | `<TICKET> [note...]` |
| `/feature-dev-aidd:implement` | Iterative implementation | `<TICKET> [note...]` |
| `/feature-dev-aidd:review` | Code review + handoff tasks | `<TICKET> [note...]` |
| `/feature-dev-aidd:qa` | Final QA check | `<TICKET> [note...]` |
| `/feature-dev-aidd:status` | Ticket status summary | `[<TICKET>]` |

## Documentation
- [AGENTS.md](AGENTS.md) - repo dev policy and source-of-truth map.
- [README.md](README.md) - Russian version of this README.
- [docs/runbooks/prod-like-breaking-migration.md](docs/runbooks/prod-like-breaking-migration.md) - migration runbook for breaking path changes.
- [docs/agent-skill-best-practices.md](docs/agent-skill-best-practices.md) - skill authoring best practices.
- [docs/skill-language.md](docs/skill-language.md) - language and lint policy for prompts and skills.
- [docs/memory-v2-rfc.md](docs/memory-v2-rfc.md) - draft RFC for Memory v2.

## Prerequisites
- `python3`, `rg`, `git`.
- Claude Code with plugin marketplace access.
- For maintainer checks: `shellcheck`, `markdownlint`, `yamllint`.

## Contributing
Contribution process: [CONTRIBUTING.md](CONTRIBUTING.md).

## License
MIT, see [LICENSE](LICENSE).
