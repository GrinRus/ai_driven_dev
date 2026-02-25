# Release Notes

## Unreleased

### Breaking Changes
- Wave 96 shell-runtime cutover: `tools/*.sh` entrypoints are removed from public runtime API.
- Wave 97 Python-only runtime canon: canonical runtime API is now `python3 skills/*/runtime/*.py`.
- `skills/*/scripts/*.sh` moved to transition-only compatibility layer (deprecation window through 2026-03-31).
- `tools/*.py` remains as shared Python runtime library; new integrations must target Python entrypoints.
- Removed deprecated runtime CLI `skills/aidd-core/runtime/researcher_context.py`.
- Removed legacy retry alias `--answers` from `skills/spec-interview/runtime/spec_interview.py`.
- Removed legacy no-op flag `--refresh` from `skills/review/runtime/context_pack.py`.
- Removed legacy runtime entrypoint `skills/review/runtime/context_pack.py` and dropped `context-pack` compatibility wiring from repo test harness.
- Removed deprecated `reports_pack` compatibility APIs `build_research_context_pack` and `write_research_context_pack`.
- Runtime facades for `loop_step`, `loop_run`, `loop_pack`, `tasklist_check`, `tasks_derive`, `reports_pack`, and `qa` now load split implementations from `runtime/*_parts/core.py`.

### New Features
- Wave 101 PR-07/PR-08 (AST optional retrieval): researcher pipeline now produces `aidd/reports/research/<ticket>-ast.pack.json`, uses deterministic `ast-index -> rg` fallback in `auto`, and blocks with `next_action` in `required`.
- Plan/review-spec gates now consume AST evidence in non-blocking optional mode; missing/invalid AST packs are warnings in `auto` and deterministic blocks in `required`.
- Doctor adds wave-2 rollout diagnostics for AST expansion (`ast_index.rollout_wave2`) with threshold checks for quality/latency/fallback-rate and `decision_mode` (`advisory|hard`).
- Wave 101 PR-04/PR-05 (Memory v2): added `skills/aidd-memory/runtime/{memory_extract,decision_append,memory_pack,memory_slice,memory_verify}.py` workflow coverage with canonical artifacts `aidd/reports/memory/<ticket>.semantic.pack.json` and `<ticket>.decisions.pack.json`.
- Loop DocOps now supports validated decision writes through `memory_ops.decision_append` (actions schema + stage contracts + preflight defaults).
- Gate/readiness adds soft/hard memory checks (`memory_semantic_pack_missing*`, `memory_decisions_pack_missing*`) for `plan/review/qa`.
- Smoke workflow now validates Memory v2 lifecycle end-to-end (extract/verify/append/pack/slice).
- Wave 102 (Memory usage alignment): added stage-aware autoslice runtime `skills/aidd-memory/runtime/memory_autoslice.py` plus manifests `aidd/reports/context/<ticket>-memory-slices.<stage>.<scope_key>.pack.json` and latest slice aliases.
- Read-discipline hardening: `research/plan/review-spec/implement/review/qa` now materialize memory slice manifests; output contract checks read order and emits deterministic reason codes (`memory_slice_missing`, `memory_slice_stale`, `memory_slice_manifest_missing`, `rg_without_slice`).
- Controlled `rg` fallback is enforced by context guards (`rg_guard`/`bash_guard` integration): `rg` without fresh slice manifest becomes `ask/deny` by policy mode.
- Memory decision freshness: `memory_ops.decision_append` triggers same-run `decisions.pack` refresh and stale events are tracked with `memory_decisions_pack_stale`.
- Observability extension: `aidd.context_quality.v1` now tracks `memory_slice_reads`, `rg_invocations`, `rg_without_slice_rate`, `decisions_pack_stale_events`; doctor adds `memory.rollout_hardening` threshold diagnostics.
- `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh` for environment/path diagnostics and workspace checks.
- Test profiles `fast/targeted/full/none` via `aidd/.cache/test-policy.env` and `AIDD_TEST_*` flags for `format-and-test.sh`.
- Dedupe cache `aidd/.cache/format-and-test.last.json` to avoid repeating test runs when diff/profile are unchanged.
- Loop mode (Ralph): `loop-pack`, `review-pack`, `diff-boundary-check`, `loop-step`, `loop-run` with loop packs and loop discipline.
- Architecture Profile templates (`aidd/docs/architecture/profile.md`).
- Stack detection for init (`/feature-dev-aidd:aidd-init --detect-build-tools`).
- `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh` to validate research artefacts before planning.
- PRD template section `## AIDD:RESEARCH_HINTS` for passing paths/keywords to `/feature-dev-aidd:researcher`.
- New review-plan stage with `plan-reviewer`, `## Plan Review` in plans, and a `plan_review` gate.
- SDLC contract docs: `aidd/docs/sdlc-flow.md` and `aidd/docs/status-machine.md`.
- `aidd/AGENTS.md` as the primary agent entrypoint.
- Plan template (`aidd/docs/plan/template.md`) with mandatory executability sections.
- QA gate: `aidd/hooks/gate-qa.sh`, heuristic agent via `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh`, and `aidd/agents/qa.md` with severity guidance.
- CI now executes the QA gate (`.github/workflows/ci.yml`) with diff-aware analysis (`QA_AGENT_DIFF_BASE`).
- Analyst dialog enforcement: updated `aidd/agents/analyst.md`, PRD template with `## Диалог analyst`, script `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh`, gate-workflow integration, smoke coverage, and docs/tests showing the `Ответ N:` workflow.
- Progress tracking: script `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`, new `tasklist_progress` gate in `config/gates.json`, gate-workflow integration, smoke coverage, and unit tests validating missing/updated checkboxes.
- Iteration guidance updated for implementer/reviewer/qa agents, tasklist template guidance (`Checkbox updated: …`), and docs (`README`, `AGENTS.md`) reflecting the mandatory tasklist sync.
- Auto PRD scaffolding: `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh` and `tools/feature_ids.py` now create `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`, so agents/gates always work against an existing artefact.
- Runtime workflow tools: `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh`, `plan-review-gate`, `prd-review-gate`, `research`, and `context-gc-*.sh`.
- Agent-first documentation set: updated `/feature-dev-aidd:idea-new`, prompt templates (see `AGENTS.md`), PRD/tasklist/research templates, README (RU/EN), and `AGENTS.md`, ensuring agents log repository inputs and script commands before asking the user.

### Improvements
- Wave 102 completed: all 19 `skills/*/SKILL.md` converged to shared contract structure (`name` baseline, compact `Command contracts`, deterministic `Additional resources` with `when/why`), stage loop policy wording now uses stable semantic markers, and prompt-lint/policy tests were hardened for semantic contract checks.
- Wave backlog discipline: each wave now has a single active status source-of-truth; historical sections must be marked as archive (non-SoT), and smoke checks guard against conflicting active statuses.
- `spec-interview` stage chain now explicitly invokes subagent `feature-dev-aidd:spec-interview-writer`, with lint and prompt-test enforcement.
- Repository topology audit now renders findings from actual graph/triage data and excludes active Draft docs from `unused.candidates` when they have open references in `backlog.md`.
- Skill-first prompts: canonical runtime policy moved to `skills/aidd-core`/`skills/aidd-loop`, stage entrypoints defined by skills, fallback command docs moved to `docs/fallback/commands`, and CI now guards skills/entrypoints parity.
- Added Phase-2 redirect-wrapper removal blueprint with rollback criteria (`docs/fallback/commands/redirect-wrapper-removal-plan.md`) including review redirect-wrapper transition windows.
- Docs and prompts now use namespaced slash commands (`/feature-dev-aidd:*`) for marketplace installs.
- Evidence Read Policy (RLM-first) and context precedence blocks aligned across prompts and anchors.
- Prompt regression checks and architecture profile validation in repo CI.
- AIDD no longer bundles runbook guidance; prompts now rely on user-provided steps for test/format/run.
- `format-and-test.sh` is loop-aware: review skips, loop-mode test gating, and per-run logs in `aidd/reports/tests`.
- Marketplace manifest uses a GitHub source for the plugin, and `plugin.json` now includes author/repository/homepage/license metadata.
- Marketplace-only distribution: replaced `claude-workflow` CLI with `${CLAUDE_PLUGIN_ROOT}/tools/*.sh` entrypoints; payload sync/upgrade and release packaging removed.
- `/feature-dev-aidd:implement` and `implementer` prompts now require a test policy, iteration budget, and report `Test profile`/`Tests run` in the response.
- `format-and-test.sh` selects tasks by profile (`fastTasks/fullTasks/targetedTask`) and honors `AIDD_TEST_FORCE` when repeating runs.
- `/feature-dev-aidd:idea-new` no longer triggers research; analyst captures `AIDD:RESEARCH_HINTS`, research is run in `/feature-dev-aidd:researcher`.
- `analyst-check` no longer validates research; research validation is handled by `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh` and `gate-workflow`.
- `/feature-dev-aidd:plan-new` now runs `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh` before planning.
- Canonical flow now includes plan review: idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa.
- Commands are thin orchestrators; agents carry algorithms/stop-conditions with a unified question format (Blocker/Clarification + rationale/options/default).
- Output contract standardized (`Checkbox updated` + `Status` + `Artifacts updated` + `Next actions`), search unified on `rg`.
- Research/tasklist/QA templates updated with Context Pack, AIDD:NEXT_3, AIDD:HANDOFF_INBOX, and QA traceability to AIDD:ACCEPTANCE.
- `gate-workflow` and smoke/tests updated to enforce review-plan before PRD review/tasklist.
- Tasklist артефакты перемещены в `aidd/docs/tasklist/<ticket>.md`: обновлены шаблоны, init/CLI команды, гейты, тесты и документация; fallback `tasklist.md` больше не мигрируется автоматически.
- `set-active-feature` больше не нормализует front-matter tasklist и не переносит fallback `tasklist.md`.
- Workflow, commands, и агентские инструкции переведены на ticket-first модель (`--ticket`, `aidd/docs/.active_ticket`, slug-hint как опциональный контекст); обновлены README, `AGENTS.md` и шаблоны tasklist.
- `prd-review-gate`, smoke tests, и `analyst-check` теперь трактуют `Status: draft` как черновой PRD, блокируя коммиты до заполнения диалога и обновления статусов.
- Hooks call `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh` and runtime tools call `${CLAUDE_PLUGIN_ROOT}/tools/*.sh`; no `claude-workflow` dependency.
- `tests/repo_tools/ci-lint.sh` запускает линтер промптов, dry-run `tests/repo_tools/prompt-version`, новые тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_versioning.py`) и smoke/gate-workflow проверки.
- Analyst/researcher/implementer prompts now require citing checked files and executed commands (`rg`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`, `<test-runner> <args>`), while tasklist/research templates embed `Commands/Reports` blocks so downstream agents inherit reproducible context.
- Prompt specs now standardize PRD/PRD Review statuses to `READY/BLOCKED/PENDING`, accept free-form notes after the ticket in every command, and align `allowed-tools` with subagent requirements.
- `idea-new` UX no longer requires user-provided `slug-hint`: command contract is now `<ticket> [note...]`, and internal `slug_hint` is generated from `idea_note` summary before `set_active_feature.py --slug-note`.
- Prompt linting validates duplicate front matter keys, disallowed statuses, HTML-escaped `<ticket>`, `Checkbox updated` placement hints, and tool parity across paired prompts.
- Внутренний backlog (`backlog.md`) оставлен dev-only и исключён из marketplace-плагина; lint/check скрипты больше не ожидают каталог `doc/`.

### Fixes
- `gate-workflow` hardened reviewer fallback path resolution: no secondary crashes when `tools.runtime` import fails.
- `aidd-init` CLI simplified: removed `--dry-run` and `--enable-ci`; supported flags are now `--force`, `--detect-build-tools`, and hidden alias `--detect-stack`.
- Smoke/docs moved to canonical review wrappers in `skills/review/scripts/*`; phased-out `tools/review-*.sh` redirect-wrappers remain transition-only with warnings.
- Reviewer marker migration is centralized in `tools/runtime.py`; duplicate migration logic removed from hook/CLI paths.
- Preflight artifacts now use canonical loop/context paths only; fallback preflight read/write compatibility paths were removed from runtime and gate checks.
- CI now includes an always-on `smoke-workflow` job (auto-skip when runtime paths are unchanged) and PR dependency review (`actions/dependency-review-action`).
- Marketplace metadata is pinned to stable `main`; `ci-lint` now blocks feature refs like `codex/wave*` and `feature/*`.
- Removed `gate-api-contract` placeholder hook and deleted tracked ad-hoc audit prompt file from the repo.
- Updated `aidd` snapshot to match marketplace scripts and docs (removed stale `claude-workflow` references).
- RLM bootstrap nodes option to unblock finalize when nodes are missing, plus clearer guard/linker hints.
- Tasklist spec-required checks now cover API/DATA/E2E signals and tasklist runs `tasklist-check` post-refine.
- QA test sourcing updated to README/CI discovery (no default smoke command), with stricter missing-tests handling.
- Implement loop boundary violations now require BLOCKED status and out-of-scope backlog entry.

## v0.1.0 (2025-02-XX)

### New Features
- Initial release of `claude-workflow-cli` packaging and installation instructions.
