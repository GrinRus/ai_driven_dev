# AIDD Improvement Plan (Roadmap)

## Goals (measurable)
- Stage lexicon single SoT: `0` conflicts между `stage-lexicon`, runtime validators, setters и planning guards.
- Prompt governance green: `tests/repo_tools/ci-lint.sh` проходит без prompt-lint ошибок (`missing policy/baseline = 0`).
- Templates governance: `1` canonical source for workspace content templates; docs and init implementation aligned.
- Skill quality: `100%` skills имеют явный trigger phrase (`Use when ...` / equivalent) и actionable steps where applicable.
- Subagent safety: `100%` agents имеют явные ограничения (`permissionMode` strategy + `disallowedTools` or documented waiver).
- Migration closure: `0` tracked-but-missing runtime entrypoints; `0` stale references to retired `tools/*.sh` runtime API.
- CI/security parity: documented gates == enforced checks; add at least `2` security controls beyond dependency review.

## Workstreams/Epics (5–8)

### WS1. Canonical SoT Consolidation
- Why: F-001, F-002, F-011
- Scope:
  - Define single canonical template source for stage artifacts.
  - Align `AGENTS.md`, `README*`, `aidd-init/runtime/init.py` with that source.
  - Remove stale root-path references (`tools/`, `docs/`) from user/dev docs.
- Out of scope:
  - Functional redesign of stage logic.
- Risks:
  - Breaking existing contributor habits tied to old file paths.
- Dependencies:
  - WS3 (prompt-lint policy update) for green CI.
- Migration strategy:
  - Canonical path declaration -> deprecation notice -> short compatibility window -> remove stale path references.
- Success metrics:
  - No doc/runtime SoT conflicts in audit checklist.

### WS2. Stage Lexicon Unification
- Why: F-004, F-005, F-006
- Scope:
  - Centralize stage enum in one runtime module.
  - Make `set_active_stage`, context validators, guards consume the same enum/alias map.
  - Fix `spec-interview` stage assignment and remove unsupported `release` placeholder.
- Out of scope:
  - New business stages beyond current workflow.
- Risks:
  - Backward compatibility for old aliases (`spec`, `tasks`).
- Dependencies:
  - WS1 (SoT clarity), WS5 (hook behavior depends on stage semantics).
- Migration strategy:
  - Canonical stage map + explicit alias mapping + warning window + strict mode cutoff.
- Success metrics:
  - `set-active-stage`, `context-map-validate`, and guards accept/reject identical stage semantics.

### WS3. Prompt-Lint Baseline Rehabilitation
- Why: F-003
- Scope:
  - Restore/migrate `docs/skill-language.md` policy location.
  - Restore or relocate `commands_to_skills_frontmatter.json` baseline and update linter constants.
  - Ensure stage baseline entries exist for all stage skills.
- Out of scope:
  - New lint rule design.
- Risks:
  - False-green by relaxing rules instead of fixing canonical data.
- Dependencies:
  - WS1 (path decisions).
- Migration strategy:
  - Add compatibility lookup paths first, then hard-switch to canonical path.
- Success metrics:
  - `tests/repo_tools/ci-lint.sh` green on prompt lint section.

### WS4. Permission & Tool-Surface Hardening
- Why: F-008, F-009, F-010
- Scope:
  - Reduce broad `allowed-tools` in high-risk skills.
  - Add agent-specific `disallowedTools` and/or stricter `permissionMode` where feasible.
  - Add trigger-quality and least-privilege checks to linter.
- Out of scope:
  - Removing required build/test commands from implement/review/qa.
- Risks:
  - Over-restriction can slow developer workflow.
- Dependencies:
  - WS2 (stage behavior stable), WS3 (lint baselines).
- Migration strategy:
  - Introduce warnings first -> tighten to errors after 1 release window.
- Success metrics:
  - Reduced risky tools count for top 3 skills; no new over-privileged agent profiles.

### WS5. Hook/Gate Surface Cleanup
- Why: F-007
- Scope:
  - Decide fate of `hooks/gate-prd-review.sh` (wire explicitly or remove).
  - Keep a single authoritative PRD gate path (direct hook vs gate-workflow internal).
- Out of scope:
  - Full hook architecture rewrite.
- Risks:
  - Double-gating or missing-gating regressions.
- Dependencies:
  - WS2 (stage/gate consistency).
- Migration strategy:
  - Add test coverage for chosen path and deprecate alternate path.
- Success metrics:
  - No unwired gate scripts in hook inventory.

### WS6. Migration Closure for Legacy Paths
- Why: F-011, F-012
- Scope:
  - Finish rename/removal of legacy `tools/*.sh` tracked paths.
  - Align repo tooling script names (`shim-regression` -> `runtime-path-regression`) across docs/commands.
  - Ensure index and filesystem are consistent.
- Out of scope:
  - Reintroducing old tool wrappers.
- Risks:
  - Partial rename states in long-lived branches.
- Dependencies:
  - WS1 (documentation updates).
- Migration strategy:
  - Hard-remove stale tracked paths after compatibility notice.
- Success metrics:
  - `tracked missing runtime paths = 0`.

### WS7. CI/Security Expansion
- Why: F-012
- Scope:
  - Add security jobs (e.g., secret scan, static analysis, SBOM generation).
  - Define required checks parity with documented release checklist.
- Out of scope:
  - Enterprise compliance frameworks.
- Risks:
  - Longer CI runtime and potential noisy findings.
- Dependencies:
  - WS3 (stable baseline paths avoid flaky CI).
- Migration strategy:
  - Add non-blocking mode first, then promote to required checks.
- Success metrics:
  - Security jobs run on PR with actionable outputs and stable signal/noise ratio.

## Backlog table
| ID | Priority | Title | Description | Affected areas/files | Acceptance criteria | Regression/tests commands | Effort | Risk | Notes |
|---|---|---|---|---|---|---|---|---|---|
| B-001 | P0 | Declare template canonical SoT | Choose single canonical source for workspace content templates and align bootstrap/docs | `AGENTS.md`, `README.md`, `README.en.md`, `skills/aidd-init/runtime/init.py`, `templates/aidd/**`, `skills/*/templates/*` | SoT statement appears once and matches runtime copy logic | `python3 tests/repo_tools/lint-prompts.py --root .` | M | Med | Links F-001/F-002 |
| B-002 | P0 | Repair prompt policy paths | Restore or remap `docs/skill-language.md` and migration baseline JSON | `tests/repo_tools/lint-prompts.py`, policy/baseline artifacts | `ci-lint` no longer reports missing policy/baseline | `tests/repo_tools/ci-lint.sh` | M | Med | Links F-003 |
| B-003 | P0 | Unify stage enum module | Central enum + alias map reused by setter/validators/guards | `skills/aidd-core/runtime/set_active_stage.py`, `skills/aidd-core/runtime/context_map_validate.py`, `hooks/context_gc/pretooluse_guard.py`, `skills/aidd-core/templates/stage-lexicon.md` | No stage conflicts in automated stage-consistency test | `python3 -m pytest -q tests/test_set_active_stage.py tests/test_wave93_validators.py` | M | Med | Links F-004 |
| B-004 | P0 | Fix spec-interview stage assignment | Replace `spec` with canonical `spec-interview` (or explicit alias normalization) | `skills/spec-interview/SKILL.md`, stage normalization code | `set-active-stage` path used by spec-interview succeeds | `python3 -m pytest -q tests/test_set_active_stage.py` | S | Low | Links F-005 |
| B-005 | P1 | Remove unsupported `release` from tasklist template | Align template stage placeholders with runtime lexicon | `skills/tasks-new/templates/tasklist.template.md` | Template contains only supported canonical/alias values | `python3 -m pytest -q tests/test_tasklist_check.py` | S | Low | Links F-006 |
| B-006 | P1 | Resolve PRD gate hook ambiguity | Wire `gate-prd-review.sh` or remove it and keep single gate path | `hooks/hooks.json`, `hooks/gate-prd-review.sh`, `skills/aidd-core/runtime/gate_workflow.py` | Hook inventory has no unwired PRD gate artifacts | `python3 -m pytest -q tests/test_gate_prd_review.py tests/test_gate_workflow.py` | S | Low | Links F-007 |
| B-007 | P1 | Harden agent permissions | Add `disallowedTools`/explicit limits and tighten tool sets per role | `agents/*.md` | High-risk agents have explicit deny/limit policy | `python3 tests/repo_tools/lint-prompts.py --root .` | M | Med | Links F-008 |
| B-008 | P1 | Reduce high-risk skill tool scope | Narrow generic Bash and Write/Edit where wrappers exist | `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, related wrappers | Risky tool counts reduced without breaking workflow | `python3 -m pytest -q tests/test_cli_subcommands.py tests/test_gate_workflow.py` | M | Med | Links F-009 |
| B-009 | P1 | Improve skill trigger descriptions | Add explicit trigger phrases (`Use when ...`) for routing quality | `skills/*/SKILL.md` | All skills pass trigger-specific lint rule | `python3 tests/repo_tools/lint-prompts.py --root .` | S | Low | Links F-010 |
| B-010 | P1 | Close legacy tracked-path drift | Remove tracked-but-missing legacy entrypoints and finalize rename set | git index + runtime path references | `tracked missing runtime paths = 0` | `bash tests/repo_tools/runtime-path-regression.sh` | M | Med | Links F-011 |
| B-011 | P1 | Normalize regression script naming | Replace stale `shim-regression` references with `runtime-path-regression` everywhere | docs/scripts/CI references | No mentions of removed script path remain | `rg -n "shim-regression\.sh" -S .` | S | Low | Links F-012 |
| B-012 | P2 | Expand security CI | Add secret scan/SAST/SBOM and rollout policy | `.github/workflows/ci.yml` (+ new workflows) | Security jobs execute on PR and publish artifacts | `act`/GitHub Actions runs + `tests/repo_tools/ci-lint.sh` | M | Med | Links F-012 |

