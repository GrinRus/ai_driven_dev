#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf '[release-readiness] %s\n' "$*"
}

log "checking manifest parity and release governance"
python3 tests/repo_tools/release_manifest_guard.py --root .

log "validating plugin and marketplace manifests"
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json

log "validating dist manifest"
python3 tests/repo_tools/dist_manifest_check.py --root .

log "running repo checks"
tests/repo_tools/ci-lint.sh

log "running smoke workflow"
tests/repo_tools/smoke-workflow.sh

log "release readiness passed"
