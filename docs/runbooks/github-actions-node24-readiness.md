# GitHub Actions Node24 Readiness

> INTERNAL/DEV-ONLY: migration plan for Node20 action deprecation on GitHub-hosted runners.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

## Trigger
GitHub will default JavaScript actions to Node24 on June 2, 2026.

## Current policy
- Critical workflows use full commit SHA pinning.
- Security and release path actions are prioritized for compatibility validation.
- Last verification checkpoint: `tests/repo_tools/ci-lint.sh` passed on 2026-04-12.

## Migration checklist
1. Track current actions in `.github/workflows/*.yml` and pin updates via Dependabot PRs.
2. For each pinned action, confirm Node24 support in upstream release notes.
3. Open a dedicated PR with action pin updates and confirm required CI jobs stay green (`dist-check`, `lint-and-test`, `smoke-workflow`, `dependency-review`, `security-secret-scan`, `security-sast`).
4. Validate release path with existing repository checks (`python3 tests/repo_tools/release_guard.py --root .`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`).
5. Resolve incompatible actions by upgrading to Node24-compatible pinned commits and re-running the checks above.

## Exit criteria
- No Node20 deprecation warnings in CI/release runs.
- Required checks on `main` remain green with Node24 execution.
