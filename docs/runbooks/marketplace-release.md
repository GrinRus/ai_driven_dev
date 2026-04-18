# Marketplace Release Runbook

> INTERNAL/DEV-ONLY: maintainer checklist for self-hosted release and official marketplace tracking.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

## Purpose
- Keep self-hosted release deterministic (`vX.Y.Z` tags only)
- Track official Anthropic marketplace submission in parallel

## Self-hosted Release (`vX.Y.Z`)
1. Ensure manifest/changelog parity:
   - `.claude-plugin/plugin.json` -> `version = X.Y.Z`
   - `.claude-plugin/marketplace.json` -> description present and plugin version/ref aligned to `vX.Y.Z`
   - `CHANGELOG.md` -> heading `## X.Y.Z - YYYY-MM-DD`
2. Run local gates:
   - `claude plugin validate .`
   - `claude plugin validate .claude-plugin/plugin.json`
   - `python3 tests/repo_tools/release_guard.py --root .`
   - `python3 tests/repo_tools/release_docs_guard.py --root .`
   - `tests/repo_tools/ci-lint.sh`
   - `tests/repo_tools/smoke-workflow.sh`
3. Merge release PR after required checks are green.
4. Tag the merge commit:
   - `git tag -a vX.Y.Z -m "Release vX.Y.Z" <merge_commit_sha>`
   - `git push origin vX.Y.Z`
5. Verify `.github/workflows/release-self-hosted.yml` and `gh release view vX.Y.Z --repo GrinRus/ai_driven_dev`.

## Official Marketplace Tracking
1. Prepare listing metadata bundle.
2. Submit official marketplace inclusion request.
3. Submit pre-built plugin listing.
4. Track reviewer feedback and follow-up PRs.
5. Record approval date and final listing URL.

## Required Policy Checks
- Branch protection on `main` keeps required checks:
  - `dist-check`, `lint-and-test`, `smoke-workflow`, `dependency-review`, `security-secret-scan`, `security-sast`
- Repository variable `AIDD_SECURITY_ENFORCE=1`
- Tag ruleset for `refs/tags/v*` blocks delete and non-fast-forward updates

## Flow Integrity Sign-off
Before tagging `vX.Y.Z`, attach green evidence for:
1. `tests/repo_tools/ci-lint.sh`
2. `tests/repo_tools/smoke-workflow.sh`
3. `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py`
4. `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/test_stage_actions_run.py tests/test_stage_result.py tests/test_research_check.py tests/test_research_command.py tests/test_tasklist_check.py tests/test_tasks_new_runtime.py tests/test_qa_agent.py tests/test_qa_exit_code.py`

If any command fails, release is blocked and rollback severity follows `docs/runbooks/tst001-audit-hardening.md`.
