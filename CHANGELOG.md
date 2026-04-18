# Release Notes

## Unreleased
- No user-facing changes yet.

## 0.1.1 - 2026-04-17
- Runtime and audit stabilization closure for waves `120`, `121`, `136` (core contracts, prompt/audit determinism, release-gate alignment).
- Wave 148 artifact truthfulness hardening for non-research surfaces:
  - added shared truth evaluator for `tasklist`/`index`/`status`;
  - split `ExpectedReports` from actual `reports` in derived state;
  - added soft `artifact_truth` policy knob and consumer-side event de-noise for repeated `gate-tests warn`.
- Added closure runbook and baseline evidence for stabilization sign-off:
  - `docs/archive/runbooks/w120-w121-w136-closure.md`
  - `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`
- Breaking cleanup override (Wave 139):
  - Removed internal docs:
    - `docs/revision/repo-cleanup-manual-checks.md`
    - `docs/runbooks/github-actions-node24-readiness.md`
  - Removed runtime helper symbols:
    - `aidd_runtime.reports.loader.get_report_paths`
    - `aidd_runtime.runtime.read_active_last_review_report_id`
    - `aidd_runtime.stage_lexicon.normalize_stage_list`
    - `aidd_runtime.test_settings_defaults.detect_build_tools`
    - `aidd_runtime.test_settings_defaults.test_settings_payload`
- Stabilized `idea-new` retry closure semantics so partial retry materialization no longer reports optimistic completion and the retry path stays truthful in audit/status surfaces.

## 0.1.0 - 2026-03-10
- First public self-hosted release of `feature-dev-aidd`.
- Self-hosted marketplace uses immutable Git tags in `.claude-plugin/marketplace.json` (`source.ref=vX.Y.Z`).
- Added tag-driven GitHub release workflow (`.github/workflows/release-self-hosted.yml`) and parity guard (`tests/repo_tools/release_guard.py`).
