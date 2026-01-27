#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

err() {
  printf '[error] %s\n' "$*" >&2
  STATUS=1
}

check_present() {
  local pattern="$1"; shift
  local scope=("$@");
  if ! rg -q "$pattern" "${scope[@]}"; then
    err "missing pattern: ${pattern} (scope: ${scope[*]})"
  fi
}

check_absent() {
  local pattern="$1"; shift
  local scope=("$@");
  if rg -n "$pattern" "${scope[@]}"; then
    err "forbidden pattern found: ${pattern}"
  fi
}

check_absent "Graph Read Policy" "${ROOT_DIR}/agents" "${ROOT_DIR}/commands" \
  "${ROOT_DIR}/templates/aidd/docs/anchors" "${ROOT_DIR}/templates/aidd/AGENTS.md" \
  "${ROOT_DIR}/templates/root/AGENTS.md"

check_present "Evidence Read Policy" "${ROOT_DIR}/agents" "${ROOT_DIR}/commands" \
  "${ROOT_DIR}/templates/aidd/docs/anchors" "${ROOT_DIR}/templates/aidd/AGENTS.md" \
  "${ROOT_DIR}/templates/root/AGENTS.md"

check_present "aidd/docs/architecture/profile.md" "${ROOT_DIR}/agents" \
  "${ROOT_DIR}/templates/aidd/docs/anchors" "${ROOT_DIR}/templates/aidd/AGENTS.md" \
  "${ROOT_DIR}/templates/root/AGENTS.md"

check_present "rlm-slice.sh" "${ROOT_DIR}/agents" "${ROOT_DIR}/commands" \
  "${ROOT_DIR}/templates/aidd/docs/anchors" "${ROOT_DIR}/templates/aidd/AGENTS.md"

stage_commands=(
  idea-new
  researcher
  plan-new
  tasks-new
  spec-interview
  review-spec
  implement
  review
  qa
)

context_pack_template="${ROOT_DIR}/templates/aidd/reports/context/template.context-pack.md"
if [[ ! -f "${context_pack_template}" ]]; then
  err "context pack template missing: ${context_pack_template}"
else
  if ! rg -q "arch_profile: aidd/docs/architecture/profile.md" "${context_pack_template}"; then
    err "context pack template missing arch_profile path"
  fi
fi

for cmd in "${stage_commands[@]}"; do
  path="${ROOT_DIR}/commands/${cmd}.md"
  if ! rg -q "aidd/reports/context/template.context-pack.md" "$path"; then
    err "${cmd}: missing context pack template reference"
  fi
done

prd_required_commands=(
  plan-new
  review-spec
  tasks-new
  implement
)

for cmd in "${prd_required_commands[@]}"; do
  path="${ROOT_DIR}/commands/${cmd}.md"
  if ! rg -q "prd-check.sh" "$path"; then
    err "${cmd}: missing prd-check.sh reference"
  fi
done

exit $STATUS
