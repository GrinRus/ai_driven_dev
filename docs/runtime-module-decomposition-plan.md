# Runtime Simplification Note

> INTERNAL/DEV-ONLY: compact maintenance policy for oversized runtime modules.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: archive-candidate

This file replaces the old “split files into `*_parts/`” plan.

Current policy:
- reduce cognitive complexity first, file count second;
- do not introduce `exec` facades or extra wrapper layers just to satisfy LOC limits;
- prefer removing indirection, duplicate helpers, and legacy branches before creating new internal packages;
- keep CLI names, report schemas, and canonical runtime entrypoints stable while simplifying internals.

Validation remains unchanged:
- `python3 tests/repo_tools/runtime-module-guard.py`
- `tests/repo_tools/ci-lint.sh`
- `tests/repo_tools/smoke-workflow.sh`
