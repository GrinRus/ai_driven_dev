# Example: reviewer (REVISE)

Status: WARN
Verdict: REVISE
Work item key: iteration_id=I1
Findings:
- F1 (blocking): missing error handling for payment timeout -> see aidd/reports/reviewer/ABC-123/iteration_id_I1.json
- F2 (non-blocking): missing test case for refund path -> handoff in tasklist
Fix Plan:
1) Add retry + timeout handling for payment client (scope: iteration_id=I1)
2) Add targeted test for refund path (scope: iteration_id=I1)
Artifacts updated: aidd/docs/tasklist/ABC-123.md; aidd/reports/reviewer/ABC-123/iteration_id_I1.json; aidd/reports/loops/ABC-123/iteration_id_I1/review.latest.pack.md
Tests: skipped (reason: review stage, targeted tests required only when evidence exists)
AIDD:READ_LOG: aidd/reports/loops/ABC-123/iteration_id_I1.loop.pack.md (reason: loop pack); aidd/reports/context/ABC-123.pack.md (reason: rolling context)
Blockers/Handoff: F1 -> AIDD:HANDOFF_INBOX (blocking)
Next actions: /feature-dev-aidd:implement ABC-123 (address Fix Plan)
