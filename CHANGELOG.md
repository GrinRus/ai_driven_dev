# Release Notes

## Unreleased
- No user-facing changes yet.

## 0.1.0 - 2026-03-10
- First public self-hosted release of `feature-dev-aidd`.
- Self-hosted marketplace uses immutable Git tags in `.claude-plugin/marketplace.json` (`source.ref=vX.Y.Z`).
- Added tag-driven GitHub release workflow (`.github/workflows/release-self-hosted.yml`) and parity guard (`tests/repo_tools/release_guard.py`).
