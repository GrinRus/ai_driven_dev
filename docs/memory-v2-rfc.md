# RFC: Memory v2 for AIDD (pack-first semantic memory)

Status: Draft (Active; Wave 101 source)  
Owner: feature-dev-aidd  
Updated: 2026-02-13

## 1. Problem statement

AIDD already uses external artifacts (`aidd/reports/**`, `aidd/docs/**`) and pack-first reading, but memory is fragmented across stage docs and reports. On large tasks, consistency depends on manually traversing multiple files.

Goal of Memory v2: add a small, deterministic semantic memory layer and a decision log layer, both file-based and script-managed, without breaking current RLM/loop contracts.

## 2. Goals and non-goals

### Goals
1. Keep context small: retrieval-first, no full-file scans by default.
1. Persist stable project knowledge (terms, defaults, constraints, invariants) in a dedicated memory artifact.
1. Persist key decisions in append-only log with explicit status (`active/superseded`).
1. Integrate into existing AIDD flow with minimal contract changes.
1. Keep deterministic serialization and strict budgets.

### Non-goals
1. Replacing RLM graph (`nodes/links`) for code evidence.
1. Building vector DB or external service dependency.
1. Rewriting current stage skills in one wave.

## 3. Target architecture

Memory v2 introduces two new artifacts per ticket:
1. Semantic memory pack  
Path: `aidd/reports/memory/<ticket>.semantic.pack.json`  
Purpose: stable facts/defaults/invariants in compact structured form.
1. Decision log + compact pack  
Paths:
- `aidd/reports/memory/<ticket>.decisions.jsonl` (append-only source)
- `aidd/reports/memory/<ticket>.decisions.pack.json` (top-N active decisions)

Existing layers remain:
- Session working set (hooks/context_gc)
- Rolling context pack (`aidd/reports/context/<ticket>.pack.md`)
- RLM evidence (`aidd/reports/research/<ticket>-rlm*.{json,jsonl}`)

## 4. Data contracts (MVP)

### 4.1 Semantic pack schema (`aidd.memory.semantic.v1`)

Required top-level fields:
- `schema`, `pack_version`, `type`, `kind`
- `ticket`, `slug_hint`, `generated_at`, `source_path`
- `terms` (columnar: `term`, `definition`, `aliases`, `scope`, `confidence`)
- `defaults` (columnar: `key`, `value`, `source`, `rationale`)
- `constraints` (columnar: `id`, `text`, `source`, `severity`)
- `invariants` (columnar: `id`, `text`, `source`)
- `open_questions` (list, capped)
- `stats`

Budgets:
- total <= 8000 chars
- lines <= 180
- per-section caps (10-20 entries)

### 4.2 Decisions log schema (`aidd.memory.decision.v1`)

JSONL entry fields:
- `schema`, `ts`, `ticket`, `scope_key`, `stage`
- `decision_id` (stable hash)
- `topic`
- `decision`
- `alternatives` (short list)
- `rationale`
- `source_path`
- `status` (`active|superseded|rejected`)
- `supersedes` (optional id)

Decision pack (`aidd.memory.decisions.pack.v1`) keeps:
- active decisions (top-N)
- latest superseded chain head links
- unresolved conflicts

## 5. Runtime entrypoints (new)

Add new shared skill/runtime surface:
1. `skills/aidd-memory/runtime/memory_extract.py`
- Input: ticket, optional scope/stage
- Reads: tasklist/spec/research/context pack (pack-first order)
- Writes: semantic pack
1. `skills/aidd-memory/runtime/decision_append.py`
- Input: JSON payload or flags
- Appends to `decisions.jsonl`
- Optional `--supersedes`
1. `skills/aidd-memory/runtime/memory_pack.py`
- Rebuilds `decisions.pack.json`
- Enforces budgets and deterministic ordering
1. `skills/aidd-memory/runtime/memory_slice.py`
- Query by token/topic/id
- Outputs compact slice pack in `aidd/reports/context/`
1. `skills/aidd-memory/runtime/memory_verify.py`
- Schema + budget validation

## 6. Retrieval policy (how agent should read)

Default read chain for planning/loop stages:
1. `aidd/reports/research/<ticket>-rlm.pack.json`
1. `aidd/reports/memory/<ticket>.semantic.pack.json`
1. `aidd/reports/memory/<ticket>.decisions.pack.json`
1. `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md` (loop stages)
1. `aidd/reports/context/<ticket>.pack.md`
1. on-demand slices (`rlm_slice.py`, `memory_slice.py`, `md_slice.py`)

Full document reads remain fallback-only with explicit reason in `AIDD:READ_LOG`.

## 7. Integration points in current codebase

### 7.1 Config/bootstrap
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/templates/aidd/config/conventions.json`
- add `memory` section: limits, enabled flags, read order hints.
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/templates/aidd/config/gates.json`
- add soft gate `memory.require_decisions_pack` for `plan/review/qa` (after rollout).
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-init/runtime/init.py`
- seed `reports/memory/.gitkeep` and optional template placeholders.

### 7.2 Hook/context layer
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/hooks/context_gc/working_set_builder.py`
- include tiny excerpt from semantic/decisions packs (strict char cap).
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/hooks/context_gc/pretooluse_guard.py`
- allow read access to `aidd/reports/memory/**` in loop read policy defaults.

### 7.3 Stage orchestration
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/researcher/runtime/research.py`
- after RLM readiness, trigger `memory_extract.py`.
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-loop/runtime/preflight_prepare.py`
- include semantic/decisions pack in generated readmap optional entries.
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-loop/runtime/output_contract.py`
- optional check: `AIDD:READ_LOG` includes memory pack for review/qa when enabled.

### 7.4 DocOps/actions
1. Extend `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-docio/runtime/actions_apply.py`
- optional action type: `memory_ops.decision_append`.
1. Update contracts:
- `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/implement/CONTRACT.yaml`
- `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/review/CONTRACT.yaml`
- `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/qa/CONTRACT.yaml`

Add optional memory read entries and (later) required checks behind flag.

### 7.5 Prompt/skills policy
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-policy/references/read-policy.md`
- include memory packs in recommended order.
1. Update `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-core/templates/context-pack.template.md`
- add `memory_semantic` and `memory_decisions` links in `artefact_links`.
1. Add new shared skill:
- `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/skills/aidd-memory/SKILL.md`

## 8. Rollout plan

### Wave 1 (non-breaking, opt-in)

Scope:
- add runtime tools
- generate memory artifacts only
- no hard gates

Acceptance:
- artifacts generated for active ticket
- schema validation passes
- no regressions in `ci-lint` and `smoke-workflow`

### Wave 2 (read integration)

Scope:
- include memory in read policy and readmaps
- enrich working set snippet

Acceptance:
- `AIDD:READ_LOG` often starts from packs (rlm + memory)
- no loop policy violations

### Wave 3 (soft-to-hard gates)

Scope:
- soft gate for missing decisions pack in `plan/review/qa`
- optional hard gate by config flag after soak period

Acceptance:
- stage readiness reflects memory completeness
- false-block rate below agreed threshold

## 9. Testing strategy
1. Unit tests:
- schema validation
- deterministic IDs
- trim/budget behavior
- decision supersede chain
1. Integration tests:
- research -> memory_extract
- loop preflight includes memory artifacts
- actions_apply decision append path
1. Repo tooling:
- run `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/tests/repo_tools/ci-lint.sh`
- run `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/tests/repo_tools/smoke-workflow.sh`

## 10. Risks and mitigations
1. Risk: duplicate or contradictory decisions.
- Mitigation: mandatory `status` + `supersedes`, plus pack conflict summary.
1. Risk: too many memory fields, low signal.
- Mitigation: strict caps and auto-trim with deterministic priority.
1. Risk: new gate noise.
- Mitigation: Wave 1-2 no hard blocks; hard gate only via explicit flag.
1. Risk: overlap with RLM causing confusion.
- Mitigation: clear split:
  - RLM = code graph evidence
  - Memory = semantic defaults + decision history

## 11. Definition of done (Memory v2 MVP)
1. Semantic and decisions packs exist and validate for active ticket.
1. Read policy and preflight include memory artifacts.
1. Loop stages can append decisions via controlled action path.
1. Context budgets remain within configured limits.
1. Existing pipelines pass without behavior regressions.

## 12. Suggested implementation order (first PR)
1. Add `skills/aidd-memory/runtime/*` + schemas.
1. Seed config knobs in templates.
1. Wire researcher post-step (`memory_extract`).
1. Wire optional memory reads in preflight/read policy.
1. Add tests + docs/changelog.
