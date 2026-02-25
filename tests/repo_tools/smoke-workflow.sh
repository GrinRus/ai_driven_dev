#!/usr/bin/env bash
# Thin facade for the repository smoke workflow.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${ROOT_DIR}/tests/repo_tools/smoke/main.sh" "$@"
