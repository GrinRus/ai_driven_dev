#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AIDD_LOOP_RUNNER_LOG:-}" ]]; then
  exit 1
fi

echo "$*" >> "${AIDD_LOOP_RUNNER_LOG}"
cat <<'EOF'
Status: READY
Work item key: iteration_id=I1
Artifacts updated: aidd/docs/tasklist/DEMO-1.md
Tests: profile=none
EOF
