#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONDONTWRITEBYTECODE=1

log() {
  printf '[python-only] %s\n' "$*"
}

log "runtime path regression"
bash tests/repo_tools/runtime-path-regression.sh

log "skill shell-wrapper guard"
python3 tests/repo_tools/skill-scripts-guard.py

log "bash runtime guard"
python3 tests/repo_tools/bash-runtime-guard.py

log "prompt lint (python-only canon)"
python3 tests/repo_tools/lint-prompts.py --root "$ROOT_DIR"

log "targeted python-only tests"
python3 -m pytest -q \
  tests/test_cli_subcommands.py \
  tests/test_context_expand.py \
  tests/test_loop_step.py \
  tests/test_rlm_wrappers.py \
  tests/test_runtime_launcher.py

log "python-only regression passed"
