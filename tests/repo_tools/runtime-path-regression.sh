#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

err() {
  printf '[error] %s\n' "$*" >&2
  STATUS=1
}

cd "$ROOT_DIR"

if [[ -d tools ]] && find tools -maxdepth 1 -type f -name '*.sh' | grep -q .; then
  err "tools/*.sh must be removed after tools-free shell cutover"
fi

# Canonical loop wrappers must remain in skills.
for script in \
  skills/aidd-loop/scripts/loop-step.sh \
  skills/aidd-loop/scripts/loop-run.sh \
  skills/aidd-loop/scripts/loop-pack.sh \
  skills/aidd-loop/scripts/preflight-prepare.sh \
  skills/aidd-loop/scripts/preflight-result-validate.sh \
  skills/aidd-loop/scripts/output-contract.sh; do
  if [[ ! -x "$script" ]]; then
    err "missing executable canonical wrapper: $script"
  fi
done

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
