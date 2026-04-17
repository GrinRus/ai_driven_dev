# Product Backlog Archive — Superseded / Rescope Waves 124 and 143

> INTERNAL/DEV-ONLY: archived backlog material moved out of the active planning queue.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: historical

_Archival note: these waves were moved from `docs/backlog.md` on 2026-04-18 because their original framing is no longer the active implementation plan. They are preserved for history and possible rescoping, but should not compete with the current execution queue._

## Wave 143 — Soft/Strict Dual Classification Rework (planned)

_Статус на момент архивации: plan (requires rescope). Цель — привести backlog в соответствие с фактическим состоянием: dual-classification + strict-shadow уже присутствуют в runtime/prompt contracts, поэтому remaining scope должен быть переопределён как hardening/cleanup, а не первичный rollout._

- [ ] **W143-1 (P0) Feature-flagged soft/strict classification** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_audit_contract.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - внедрить dual-classification только под явным флагом;
  - default режим оставить strict-compatible до завершения rollout.
  - execution note: не начинать до стабилизации `W145-2`, `W137-3`, `W139-5`.
  **AC:** без флага output не меняется; с флагом есть полная telemetry секция без влияния на default verdict.
  **Deps:** W145-2, W137-3, W139-5
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W143-2 (P1) Contract tests + prompt sync before rollout** `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/test_e2e_quality_prompt_contract.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `docs/e2e/*.txt`:
  - добавить contract/replay coverage до включения feature-flag по умолчанию;
  - синхронизировать prompt surface только после подтверждённой стабильности.
  **AC:** rollout защищён replay и contract-тестами до merge.
  **Deps:** W143-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 124 — OpenCode Host Adaptation (2026-04-02)

_Статус на момент архивации: plan (superseded framing). Основание — historical OpenCode-only adaptation draft; superseded by host-agnostic tracks (`Wave 147` flow-core/adapters + `Wave 146` e2e live prompts). Scope этой волны требует переименования/переноса в multi-host contract language._

- [ ] **W124-1 (P2) Host-neutral runtime and environment contract** `aidd_runtime/__init__.py`, `tests/repo_tools/cli-adapter-guard.py`, `docs/skill-language.md`, `AGENTS.md`, `tests/test_prompt_lint.py`:
  - ввести host-neutral canonical alias для plugin/runtime root, чтобы runtime help, docs examples и guards не зависели только от `CLAUDE_PLUGIN_ROOT`;
  - сохранить `CLAUDE_PLUGIN_ROOT` как compatibility alias для Claude host;
  - отделить canonical Python runtime contract от host-specific launcher examples и invocation semantics.
  **AC:** runtime entrypoints, help-output и doc examples поддерживают host-neutral env contract; Claude compatibility остаётся рабочей без special-case regressions.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py`, `python3 tests/repo_tools/cli-adapter-guard.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W124-2 (P2) Generated OpenCode commands and agents from shared source** `agents/*.md`, `skills/*/SKILL.md`, `.claude-plugin/plugin.json`, `.opencode/commands/*.md`, `.opencode/agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - определить canonical metadata source для генерации host surfaces из существующих stage commands и agent prompts;
  - генерировать OpenCode command и agent surfaces без ручного дублирования prompt content;
  - зафиксировать mapping между Claude slash commands и OpenCode command surface на одном canonical source.
  **AC:** все публичные стадии и ключевые stage agents имеют generated OpenCode host surfaces; изменения в shared prompt source воспроизводимо отражаются и в Claude, и в OpenCode layers.
  **Deps:** W124-1
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** L
  **Risk:** High

- [ ] **W124-3 (P2) OpenCode launcher, loop, and non-interactive runner parity** `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/loop_step.py`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - ввести host adapter для runner selection вместо жёсткой привязки к `claude -p`;
  - адаптировать seed-stage и auto-loop non-interactive execution под OpenCode runner path;
  - формализовать OpenCode-safe init evidence и diagnostics так, чтобы audit tooling различал host mode без branch explosion.
  **AC:** seed stages и loop runner могут запускаться через OpenCode non-interactive surface; runtime и audit не считают `claude -p` единственным допустимым launcher.
  **Deps:** W124-1, W124-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** L
  **Risk:** High

- [ ] **W124-4 (P2) Host-aware lint, smoke, and audit tooling** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - разделить canonical runtime checks и host-specific checks для Claude и OpenCode;
  - добавить host selector в smoke/audit fixtures и repo tools, где сейчас зашит Claude-only init/launcher contract;
  - исключить ложные FAIL/WARN из-за host mismatch при сохранении текущего Claude CI baseline.
  **AC:** tooling валидирует Claude и OpenCode независимо; canonical runtime checks больше не содержат Claude-only assumptions, а host-specific audit checks остаются детерминированными.
  **Deps:** W124-1, W124-2, W124-3
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W124-5 (P2) Host-aware docs and installation/distribution surfaces** `README.md`, `README.en.md`, `AGENTS.md`, `.claude-plugin/plugin.json`, `opencode.json`, `.opencode/plugins/*`, `CHANGELOG.md`:
  - отделить Claude-specific install/use path от canonical AIDD runtime model;
  - добавить OpenCode installation, usage и host-compatibility guidance;
  - явно зафиксировать supported hosts, compatibility layer и границы parity в user/dev docs и release surfaces.
  **AC:** документация и package surfaces больше не описывают AIDD как Claude-only plugin; documented install/use path присутствует и для Claude, и для OpenCode.
  **Deps:** W124-1, W124-2
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Medium
