#!/usr/bin/env bash
# Thin wrapper to reuse the payload linters against the repository root.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD_SCRIPT="${ROOT_DIR}/src/claude_workflow_cli/data/payload/aidd/scripts/ci-lint.sh"

if [[ ! -x "${PAYLOAD_SCRIPT}" ]]; then
  echo "[error] payload ci-lint script not found: ${PAYLOAD_SCRIPT}" >&2
  exit 1
fi

export CLAUDE_PROJECT_DIR="${ROOT_DIR}"
exec "${PAYLOAD_SCRIPT}" "$@"
