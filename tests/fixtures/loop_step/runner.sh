#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AIDD_LOOP_RUNNER_LOG:-}" ]]; then
  exit 1
fi

echo "$*" >> "${AIDD_LOOP_RUNNER_LOG}"
