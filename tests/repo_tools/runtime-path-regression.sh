#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

err() {
  printf '[error] %s\n' "$*" >&2
  STATUS=1
}

cd "$ROOT_DIR"

if find skills -type f -path '*/scripts/*.sh' | grep -q .; then
  err "skill shell wrappers must be removed from skills/*/scripts/*.sh"
fi

if [[ -d tools ]] && find tools -maxdepth 1 -type f -name '*.sh' | grep -q .; then
  err "tools/*.sh must be removed after tools-free shell cutover"
fi

# Canonical shared loop runtime entrypoints must exist (python-only command surface).
for entrypoint in \
  skills/aidd-loop/runtime/loop_step.py \
  skills/aidd-loop/runtime/loop_run.py \
  skills/aidd-loop/runtime/loop_pack.py \
  skills/aidd-loop/runtime/preflight_prepare.py \
  skills/aidd-loop/runtime/preflight_result_validate.py \
  skills/aidd-loop/runtime/output_contract.py; do
  if [[ ! -f "$entrypoint" ]]; then
    err "missing canonical python entrypoint: $entrypoint"
  fi
done

# Canonical stage/runtime entrypoints must exist (python-only command surface).
for entrypoint in \
  skills/aidd-init/runtime/init.py \
  skills/idea-new/runtime/analyst_check.py \
  skills/researcher/runtime/research.py \
  skills/plan-new/runtime/research_check.py \
  skills/aidd-core/runtime/prd_review.py \
  skills/spec-interview/runtime/spec_interview.py \
  skills/tasks-new/runtime/tasks_new.py \
  skills/implement/runtime/implement_run.py \
  skills/review/runtime/review_run.py \
  skills/qa/runtime/qa_run.py \
  skills/status/runtime/status.py; do
  if [[ ! -f "$entrypoint" ]]; then
    err "missing canonical python entrypoint: $entrypoint"
  fi
done

# Canonical shared flow/state runtime entrypoints must exist.
for entrypoint in \
  skills/aidd-flow-state/runtime/set_active_feature.py \
  skills/aidd-flow-state/runtime/set_active_stage.py \
  skills/aidd-flow-state/runtime/prd_check.py \
  skills/aidd-flow-state/runtime/progress.py \
  skills/aidd-flow-state/runtime/progress_cli.py \
  skills/aidd-flow-state/runtime/tasklist_check.py \
  skills/aidd-flow-state/runtime/tasks_derive.py \
  skills/aidd-flow-state/runtime/stage_result.py \
  skills/aidd-flow-state/runtime/status_summary.py; do
  if [[ ! -f "$entrypoint" ]]; then
    err "missing canonical flow-state entrypoint: $entrypoint"
  fi
done

# Canonical shared observability runtime entrypoints must exist.
for entrypoint in \
  skills/aidd-observability/runtime/doctor.py \
  skills/aidd-observability/runtime/tools_inventory.py \
  skills/aidd-observability/runtime/tests_log.py \
  skills/aidd-observability/runtime/dag_export.py \
  skills/aidd-observability/runtime/identifiers.py; do
  if [[ ! -f "$entrypoint" ]]; then
    err "missing canonical observability entrypoint: $entrypoint"
  fi
done

# Flow/state runtime must not remain in aidd-core after ownership split.
for legacy in \
  skills/aidd-core/runtime/set_active_feature.py \
  skills/aidd-core/runtime/set_active_stage.py \
  skills/aidd-core/runtime/prd_check.py \
  skills/aidd-core/runtime/progress.py \
  skills/aidd-core/runtime/progress_cli.py \
  skills/aidd-core/runtime/tasklist_check.py \
  skills/aidd-core/runtime/tasks_derive.py \
  skills/aidd-core/runtime/stage_result.py \
  skills/aidd-core/runtime/status_summary.py; do
  if [[ -f "$legacy" ]]; then
    err "legacy flow-state module must not exist in aidd-core: $legacy"
  fi
done

# Observability runtime must not remain in aidd-core after ownership split.
for legacy in \
  skills/aidd-core/runtime/doctor.py \
  skills/aidd-core/runtime/tools_inventory.py \
  skills/aidd-core/runtime/tests_log.py \
  skills/aidd-core/runtime/dag_export.py \
  skills/aidd-core/runtime/identifiers.py; do
  if [[ -f "$legacy" ]]; then
    err "legacy observability module must not exist in aidd-core: $legacy"
  fi
done

# No runtime-facing docs/prompts may point to removed stage shell wrappers.
if rg -n --pcre2 "skills/[A-Za-z0-9_.-]+/scripts/run\\.sh" \
  AGENTS.md README.md README.en.md templates/aidd hooks agents skills/*/SKILL.md skills/*/CONTRACT.yaml \
  >/tmp/aidd-run-wrapper-refs.txt 2>/dev/null; then
  err "found runtime references to legacy stage run wrappers; see /tmp/aidd-run-wrapper-refs.txt"
fi

if rg -n --pcre2 "skills/[A-Za-z0-9_.-]+/scripts/[A-Za-z0-9_.-]+\\.sh" \
  AGENTS.md README.md README.en.md templates/aidd hooks agents skills/*/SKILL.md skills/*/CONTRACT.yaml \
  >/tmp/aidd-skill-wrapper-refs.txt 2>/dev/null; then
  err "found runtime references to removed skill shell wrappers; see /tmp/aidd-skill-wrapper-refs.txt"
fi

# No runtime references to removed tools shell entrypoints.
if rg -n --pcre2 "(?<![A-Za-z0-9_])(?:\\$\\{CLAUDE_PLUGIN_ROOT\\}/)?tools/[A-Za-z0-9._-]+\\.sh" \
  AGENTS.md README.md README.en.md templates/aidd hooks skills agents tests .github/workflows \
  --glob '!tests/repo_tools/lint-prompts.py' \
  --glob '!tests/test_prompt_lint.py' \
  --glob '!tests/test_tools_inventory.py' \
  --glob '!backlog.md' >/tmp/aidd-tools-shell-refs.txt 2>/dev/null; then
  err "found stale tools/*.sh references; see /tmp/aidd-tools-shell-refs.txt"
fi

exit "$STATUS"
