# Example: qa (WARN)

Status: WARN
Work item key: ticket=ABC-123
Artifacts updated: aidd/docs/tasklist/ABC-123.md; aidd/reports/qa/ABC-123.json
Tests: run (profile: full; evidence: aidd/reports/tests/ABC-123/ticket.jsonl)
AIDD:READ_LOG: aidd/reports/context/ABC-123.pack.md (reason: rolling context); aidd/reports/qa/ABC-123.json (reason: QA report)
Blockers/Handoff: QA-1 (non-blocking) -> AIDD:HANDOFF_INBOX
Traceability: AIDD:QA_TRACEABILITY updated in aidd/docs/tasklist/ABC-123.md
Next actions: /feature-dev-aidd:implement ABC-123 (fix QA-1), then /feature-dev-aidd:review ABC-123
