# AIDD Context Pack — <stage>

ticket: <ticket>
stage: <stage>
agent: <agent>
generated_at: <UTC ISO-8601>
read_next:
- <read_next>
artefact_links:
- prd: aidd/docs/prd/<ticket>.prd.md
- plan: aidd/docs/plan/<ticket>.md (if exists)
- tasklist: aidd/docs/tasklist/<ticket>.md (if exists)
- research: aidd/docs/research/<ticket>.md (if exists)
- spec: aidd/docs/spec/<ticket>.spec.yaml (if exists)
- loop_pack: aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md (implement/review)
- review_pack: aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md (if exists)
- review_report: aidd/reports/reviewer/<ticket>/<scope_key>.json (if exists)
- qa_report: aidd/reports/qa/<ticket>.json (if exists)
- test_policy: aidd/.cache/test-policy.env (if exists)

## AIDD:READ_LOG
- <path> (reason: ...)

## What to do now
- <stage-specific goal>

## User note
- <arguments/note>

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
