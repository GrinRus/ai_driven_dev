# Artifact Quality Rubric

## Goal
Score the quality of AIDD artifacts without reimplementing the underlying truth logic.

## Canonical signal
- Use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/artifact_audit.py`.
- Read its JSON output first. Use direct file inspection only to explain findings.

## Primary finding groups
- `template_leakage`
  - Placeholder content remains in tasklists or context packs.
  - Typical examples: `<name/team>`, `<stage>`, or template-only headings that should have been resolved.
- `missing_expected_reports`
  - A tasklist advertises downstream reports that do not exist under `aidd/reports/**`.
  - This is a readiness risk, especially when the tasklist says `READY`.
- `status_drift`
  - Top-level `Status` and subsection review status disagree.
  - Treat this as a truth drift problem, not as a wording nit.
- `stale_references`
  - Front matter points to missing PRD/plan/report files.
  - Usually indicates artifact renames or incomplete stage outputs.
- readiness mismatches
  - The artifact set claims readiness while required downstream evidence is absent or contradictory.
  - Example: tasklist is `READY`, but required QA or review reports are missing.

## Review discipline
- Prefer pack files and machine-readable JSON to raw markdown inference.
- Do not mark artifacts healthy if the JSON gate is `FAIL`.
- Do not auto-rewrite artifacts in `v1`; only report the mismatch and the likely next action.
