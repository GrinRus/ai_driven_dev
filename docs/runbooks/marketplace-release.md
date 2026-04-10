# Marketplace Release Runbook

> INTERNAL/DEV-ONLY: maintainer runbook for self-hosted release and official marketplace submission tracking.

## Purpose
- Keep self-hosted release deterministic (`vX.Y.Z` tags only).
- Track official Anthropic marketplace submission in parallel.

## Self-hosted release checklist (`vX.Y.Z`)
1. Ensure manifests/changelog parity:
   - `.claude-plugin/plugin.json` -> `version = X.Y.Z`
   - `.claude-plugin/marketplace.json` -> `metadata.description` present
   - `.claude-plugin/marketplace.json` -> `plugins[].version = X.Y.Z`, `plugins[].source.ref = vX.Y.Z`
   - `CHANGELOG.md` -> heading `## X.Y.Z - YYYY-MM-DD`
2. Run local gates:
   - `claude plugin validate .`
   - `claude plugin validate .claude-plugin/plugin.json`
   - `python3 tests/repo_tools/release_guard.py --root .`
   - `python3 tests/repo_tools/release_docs_guard.py --root .`
   - `tests/repo_tools/ci-lint.sh`
   - `tests/repo_tools/smoke-workflow.sh`
3. Merge release PR to `main` after green required checks.
4. Create annotated tag `vX.Y.Z` on merge commit:
   - `git tag -a vX.Y.Z -m "Release vX.Y.Z" <merge_commit_sha>`
   - `git push origin vX.Y.Z`
5. Verify GitHub release workflow:
   - `.github/workflows/release-self-hosted.yml` run status = success
   - `gh release view vX.Y.Z --repo GrinRus/ai_driven_dev`

## Official marketplace tracking checklist
1. Prepare listing metadata bundle (name/version/source/categories/tags/description).
2. Submit official marketplace inclusion request.
3. Submit pre-built plugin listing.
4. Track reviewer feedback and follow-up PR links.
5. Record approval date and official listing URL.

## Required repository policy checks
- Branch protection on `main` keeps required checks:
  - `dist-check`, `lint-and-test`, `smoke-workflow`, `dependency-review`, `security-secret-scan`, `security-sast`.
- Repository variable `AIDD_SECURITY_ENFORCE=1`.
- Tag ruleset for `refs/tags/v*` blocks delete and non-fast-forward updates.

## Flow Integrity Sign-off (Wave 136)
Before tagging `vX.Y.Z`, release owner must attach evidence that the stabilization matrix is green:
1. `tests/repo_tools/ci-lint.sh`
2. `tests/repo_tools/smoke-workflow.sh`
3. `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py`
4. `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/test_stage_actions_run.py tests/test_stage_result.py tests/test_research_check.py tests/test_research_command.py tests/test_tasklist_check.py tests/test_tasks_new_runtime.py tests/test_qa_agent.py tests/test_qa_exit_code.py`

If any command fails, release is blocked and rollback decision follows `seed/loop/qa` incident severity from `docs/runbooks/tst001-audit-hardening.md`.
