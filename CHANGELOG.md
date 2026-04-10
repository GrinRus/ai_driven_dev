# Release Notes

## Unreleased
- Runtime and audit stabilization closure for waves `120`, `121`, `136` (core contracts, prompt/audit determinism, release-gate alignment).
- Added closure runbook and baseline evidence for stabilization sign-off:
  - `docs/runbooks/w120-w121-w136-closure.md`
  - `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`

## 0.1.0 - 2026-03-10
- First public self-hosted release of `feature-dev-aidd`.
- Self-hosted marketplace uses immutable Git tags in `.claude-plugin/marketplace.json` (`source.ref=vX.Y.Z`).
- Added tag-driven GitHub release workflow (`.github/workflows/release-self-hosted.yml`) and parity guard (`tests/repo_tools/release_guard.py`).
