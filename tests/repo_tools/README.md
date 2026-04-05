# `tests/repo_tools` Ownership And Lifecycle

> INTERNAL/DEV-ONLY: policy for repo tooling scripts and experimental utilities.

## Purpose

This directory contains repository-level tooling used by CI, release checks,
smoke workflows, and optional benchmark/evaluation scripts.

## Ownership

1. Runtime/CI-critical scripts are owned by the repository maintainers as a
required surface for `ci-lint.sh`, `smoke-workflow.sh`, and GitHub Actions.
1. Experimental scripts are owned by the authoring wave/PR until they are
either integrated into CI/docs or explicitly deprecated/removed.
1. Any removal of compatibility or experimental tooling requires explicit owner
approval in PR review.

## Lifecycle Policy

1. New script must be classified at creation time:
- `required`: part of CI/runtime contract.
- `advisory`: optional diagnostics; safe to skip in constrained env.
- `experimental`: not in required CI path yet.
1. Each `experimental` script must include:
- short usage note (arguments + output artifact),
- intended owner,
- decision deadline (integrate, archive, or delete).
1. If an experimental tool remains unreferenced by CI/docs for one planning
cycle, open an owner decision task in backlog.

## Current Experimental Set Requiring Owner Decision

1. `tests/repo_tools/trigger_eval_runner.py`
1. `tests/repo_tools/trigger_eval_compare.py`
1. `tests/repo_tools/trigger_eval_set.json`

Current status:
- no required CI integration;
- no removal is performed automatically;
- next action is owner decision: integrate into documented flow, archive, or
  remove via dedicated PR.
