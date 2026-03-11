# GitHub Actions Node24 Readiness

> INTERNAL/DEV-ONLY: migration plan for Node20 action deprecation on GitHub-hosted runners.

## Trigger
GitHub will default JavaScript actions to Node24 on June 2, 2026.

## Current policy
- Critical workflows use full commit SHA pinning.
- Security and release path actions are prioritized for compatibility validation.

## Migration checklist
1. Track current actions in `.github/workflows/*.yml` and pin updates via Dependabot PRs.
2. For each pinned action, confirm Node24 support in upstream release notes.
3. Run CI validation with `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` in a dedicated branch/PR.
4. Resolve incompatible actions by upgrading to a Node24-compatible pinned commit.
5. Remove temporary compatibility env toggles before June 2, 2026.

## Exit criteria
- No Node20 deprecation warnings in CI/release runs.
- Required checks on `main` remain green with Node24 execution.
