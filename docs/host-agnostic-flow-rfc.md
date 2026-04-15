# RFC: Host-Agnostic AIDD Flow (Claude, Pi, Generic Agents)

> INTERNAL/DEV-ONLY: draft RFC for maintainers; not part of public release onboarding.

Owner: feature-dev-aidd  
Last reviewed: 2026-04-15  
Status: active  
RFC status: Draft  
Updated: 2026-04-15

## 1. Problem statement

Current AIDD workflow is implemented as a high-governance runtime optimized for Claude plugin execution:
- stage contracts are enforced by hook chain and Python runtime entrypoints;
- readiness and loop behavior depend on strict artifact contracts under `aidd/docs/**` and `aidd/reports/**`;
- policy behavior is embedded in host-specific execution wiring.

This works well for Claude but creates friction for:
1. Running the same flow in Pi-based agents.
1. Running on other agent hosts with different capabilities (no hooks, no native subagents, different permission models).
1. Keeping behavioral parity while evolving prompts/adapters.

Goal: define a host-agnostic AIDD Flow form where business logic and contracts are host-independent, and host integrations are thin adapters.

## 2. Goals and non-goals

### Goals

1. Preserve current AIDD guarantees:
- deterministic stage chain (`preflight -> run -> postflight -> stage_result`);
- pack-first evidence policy;
- gate policies and reason-code semantics.
1. Make flow executable on Claude, Pi, and generic hosts with minimal host-specific code.
1. Keep canonical contracts file-based and CI-verifiable.
1. Add conformance tests that prove adapter parity.

### Non-goals

1. Rewriting all stage prompts/skills in one wave.
1. Replacing existing `aidd/docs/**` and `aidd/reports/**` layouts.
1. Making every host feature-identical (optional capabilities may degrade gracefully).

## 3. Architecture principles

1. Contract-first: schemas and stage semantics are source of truth.
1. Engine/adapters split: core flow engine contains policy and transitions; adapters only map host APIs to engine interface.
1. Deterministic outputs: all runtime decisions serialize into explicit artifacts/events.
1. Capability negotiation: adapters declare host capabilities; flow engine selects strict or degraded execution path explicitly.
1. Backward compatibility: existing command entrypoints remain valid during migration.

## 4. Target architecture

### 4.1 Layers

1. `flow-spec` (declarative model)
- stages, transitions, gates, required artifacts, reason-code policy.
1. `flow-contracts` (data contracts)
- JSON schemas for stage result, gate decisions, artifacts, adapter events.
1. `flow-core` (execution + policy)
- pure orchestration, gate evaluation, transition logic, fail-fast checks.
1. `host-adapters`
- Claude adapter, Pi adapter, Generic adapter.
1. `host-packages`
- optional host-native wrappers (Claude hook wiring, Pi extension glue, other host launcher scripts).

### 4.2 Proposed repository layout (phase target)

```text
skills/
  aidd-flow-core/
    SKILL.md
    runtime/
      flow_run.py
      flow_preflight.py
      flow_postflight.py
      flow_stage_result.py
      gate_eval.py
      transition_eval.py
      contract_validate.py
    references/
      flow-spec.md
      adapter-protocol.md

  aidd-flow-contracts/
    SKILL.md
    runtime/
      validate_schema.py
    schemas/
      aidd.flow.stage-result.v1.json
      aidd.flow.gate-decision.v1.json
      aidd.flow.adapter-event.v1.json
      aidd.flow.capabilities.v1.json

  aidd-host-claude/
    SKILL.md
    runtime/
      adapter_cli.py
      hooks_bridge.py

  aidd-host-generic/
    SKILL.md
    runtime/
      adapter_cli.py
      stdio_bridge.py

integrations/
  pi/
    README.md
    adapter-contract.md
    examples/
      pi-extension-bridge.ts

tests/
  conformance/
    fixtures/
    test_adapter_parity.py
    test_stage_chain_parity.py
```

Notes:
1. Canonical runtime remains Python under `skills/*/runtime/*.py`.
1. Pi-native implementation can live outside this repo; protocol compatibility is tested here through fixtures/replay.

## 5. Flow Spec and Contracts

### 5.1 Flow spec (`aidd/config/flow_spec.json`)

Minimal declarative shape:

```json
{
  "schema": "aidd.flow.spec.v1",
  "stages": ["idea", "research", "plan", "review-spec", "tasklist", "implement", "review", "qa"],
  "stage_chain": {
    "implement": ["preflight", "run", "postflight", "stage_result"]
  },
  "gates": {
    "plan": ["research_ready", "prd_ready"],
    "review": ["tasklist_progress", "tests_policy"],
    "qa": ["tests_log", "qa_contract"]
  },
  "reason_policy": {
    "FORBIDDEN": "BLOCKED",
    "NO_BOUNDARIES_DEFINED": "WARN",
    "OUT_OF_SCOPE": "WARN"
  }
}
```

### 5.2 Stage result contract

The existing stage-result semantics become explicit schema (`aidd.flow.stage-result.v1`) with required fields:
- `status`;
- `work_item`;
- `artifacts`;
- `tests`;
- `blockers`;
- `next_actions`;
- `read_log`.

This preserves current output contract checks while making them host-independent.

### 5.3 Gate decision contract

`aidd.flow.gate-decision.v1` standardizes gate outcome:
- `gate_id`;
- `stage`;
- `decision` (`PASS|WARN|BLOCK`);
- `reason_code`;
- `evidence` (artifact paths and command traces);
- `next_action`.

## 6. Adapter protocol

### 6.1 Capability declaration

Each adapter must publish capabilities:

```json
{
  "schema": "aidd.flow.capabilities.v1",
  "host": "claude|pi|generic",
  "version": "x.y.z",
  "supports": {
    "hooks": true,
    "subagents": true,
    "streaming_events": true,
    "permission_gate": true,
    "interactive_questions": true
  }
}
```

### 6.2 Runtime interface (reference)

```python
class HostAdapter(Protocol):
    def get_capabilities(self) -> dict: ...
    def run_agent_task(self, *, role: str, prompt: str, inputs: dict) -> dict: ...
    def run_command(self, *, cmd: list[str], cwd: str, env: dict | None = None) -> dict: ...
    def read_paths(self, *, paths: list[str]) -> dict: ...
    def write_paths(self, *, changes: list[dict]) -> dict: ...
    def ask_user(self, *, question: str, context: dict) -> dict: ...
    def emit_event(self, *, event: dict) -> None: ...
```

### 6.3 Degradation policy

When capability is missing, engine applies explicit fallback:
1. no `subagents` -> serial execution mode;
1. no `hooks` -> explicit gate calls before/after each stage command;
1. no `permission_gate` -> strict safe command allowlist in adapter;
1. no `interactive_questions` -> BLOCKED with structured question artifact.

Fallback decisions are logged as adapter events and included in `stage_result`.

## 7. Mapping from current implementation

Planned extraction map:
1. `hooks/gate_workflow.py` -> `aidd-flow-core/runtime/gate_eval.py`.
1. `hooks/gate-tests.sh` + policy parts -> `aidd-flow-core/runtime/gate_eval.py` test policy module.
1. `hooks/gate-qa.sh` -> `aidd-flow-core/runtime/gate_eval.py` qa policy module.
1. `skills/aidd-loop/runtime/loop_step_stage_chain.py` -> `aidd-flow-core/runtime/flow_run.py`.
1. `skills/aidd-loop/runtime/output_contract.py` -> `aidd-flow-contracts/schemas/aidd.flow.stage-result.v1.json` + validator.
1. Claude-specific hook/event glue remains in `aidd-host-claude`.

## 8. Migration plan

### Phase 0 (spec freeze)

1. Freeze current stage/gate/reason-code semantics into `flow_spec.json` + schemas.
1. Add contract validators without changing runtime behavior.

Acceptance:
- validators pass on current artifacts;
- no behavior changes in smoke tests.

### Phase 1 (core extraction)

1. Extract gate and transition logic to `aidd-flow-core`.
1. Keep existing entrypoints as compatibility wrappers.

Acceptance:
- `ci-lint` and `smoke-workflow` pass;
- compatibility wrappers produce unchanged outputs.

### Phase 2 (Claude adapter parity)

1. Introduce `aidd-host-claude` adapter and route existing hook chain through adapter interface.
1. Add conformance tests against current golden fixtures.

Acceptance:
- parity suite green for Claude;
- no regression in `gate-workflow` behavior.

### Phase 3 (Pi adapter)

1. Publish protocol docs + reference Pi bridge in `integrations/pi`.
1. Validate parity via replay fixtures and optional live integration tests.

Acceptance:
- parity suite for required capabilities green;
- degraded capability behavior is explicit and documented.

### Phase 4 (generic adapter)

1. Add stdio/CLI generic adapter.
1. Document minimum host requirements and bootstrap flow.

Acceptance:
- end-to-end run in generic mode on sample ticket;
- artifacts match required schemas.

## 9. Conformance test strategy

1. Contract tests:
- schema validation for stage_result/gate_decision/events/capabilities.
1. Behavioral parity tests:
- same input artifacts produce same gate decisions and stage transitions.
1. Adapter matrix tests:
- Claude (full capabilities), Pi (partial/full), Generic (minimal).
1. Golden fixture tests:
- fixed ticket fixtures for `idea/research/plan/implement/review/qa`.

## 10. Risks and mitigations

1. Risk: hidden host-specific assumptions in current hooks.
- Mitigation: extraction with fixture-based diffing and wrapper compatibility period.
1. Risk: dual orchestration paths during migration.
- Mitigation: single flow-core SoT; wrappers call extracted core only.
1. Risk: Pi integration drift from canonical contracts.
- Mitigation: protocol versioning + conformance suite as merge gate.
1. Risk: adapter complexity growth.
- Mitigation: strict adapter interface and capability-driven fallback rules.

## 11. Definition of done (MVP)

1. `flow_spec` and core schemas are versioned and validated in CI.
1. Claude adapter runs current flow with parity to baseline behavior.
1. Pi adapter can execute required stage chain (full or documented degraded mode).
1. Generic adapter runs minimal end-to-end flow with valid artifacts.
1. Conformance tests are required in CI for all maintained adapters.

## 12. Open decisions

1. Should Pi adapter live in this repo or external integration repo with compatibility tests only?
1. Do we version `flow_spec` independently from prompt versions, or lockstep?
1. Which capabilities are mandatory for `implement/review/qa` stages vs optional?
1. What is the sunset date for legacy hook-direct orchestration?
