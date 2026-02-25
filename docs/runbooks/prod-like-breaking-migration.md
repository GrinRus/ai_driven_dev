# Prod-like Breaking Migration Runbook

## Scope
This runbook tracks breaking path changes introduced during prod-like hardening.

## Hook entrypoint migration (`.sh` -> `.py`)

| Old path | New path |
| --- | --- |
| `hooks/context-gc-precompact.sh` | `hooks/context_gc_precompact.py` |
| `hooks/context-gc-pretooluse.sh` | `hooks/context_gc_pretooluse.py` |
| `hooks/context-gc-sessionstart.sh` | `hooks/context_gc_sessionstart.py` |
| `hooks/context-gc-stop.sh` | `hooks/context_gc_stop.py` |
| `hooks/context-gc-userprompt.sh` | `hooks/context_gc_userprompt.py` |
| `hooks/format-and-test.sh` | `hooks/format_and_test.py` |
| `hooks/gate-tests.sh` | `hooks/gate_tests.py` |
| `hooks/gate-qa.sh` | `hooks/gate_qa.py` |
| `hooks/gate-workflow.sh` | `hooks/gate_workflow.py` |
| `hooks/lint-deps.sh` | `hooks/lint_deps.py` |

## Prompt script relocation

| Old path | New path |
| --- | --- |
| `aidd_test_flow_prompt_ralph_script.txt` | `dev/prompts/ralph/aidd_test_flow_prompt_ralph_script.txt` |
| `aidd_test_flow_prompt_ralph_script_full.txt` | `dev/prompts/ralph/aidd_test_flow_prompt_ralph_script_full.txt` |

## Topology audit output migration

Default output paths for `tests/repo_tools/repo_topology_audit.py` are now:

- `aidd/.cache/revision/repo-revision.graph.json`
- `aidd/.cache/revision/repo-revision.md`
- `aidd/.cache/revision/repo-cleanup-plan.json`

`dev/reports/revision/*` is treated as generated and must not be tracked.

## CI updates required by migration

- Update all hook invocations to `hooks/*.py` names.
- Run `tests/repo_tools/ci-lint.sh` and `tests/repo_tools/smoke-workflow.sh` after path updates.
- Run `python3 tests/repo_tools/dist_manifest_check.py --root .` to verify dist surface.
