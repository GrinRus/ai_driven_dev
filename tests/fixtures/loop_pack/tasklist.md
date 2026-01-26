---
Ticket: DEMO-1
Status: READY
---

# Tasklist: DEMO-1 — loop-pack

## AIDD:ITERATIONS_FULL
- [ ] I1: Add demo feature (iteration_id: I1)
  - Goal: Add feature core
  - DoD: Feature core merged with tests passing
  - Boundaries: src/feature/**
  - Expected paths:
    - src/feature/**
  - Skills:
    - testing-pytest
  - Acceptance mapping: AC-1
  - Exit criteria:
    - core feature works
- [ ] I2: Follow-up (iteration_id: I2)
  - Goal: Add follow-up
  - DoD: Follow-up complete
  - Boundaries: src/followup/**
  - Expected paths:
    - src/followup/**
  - Skills:
    - testing-gradle
  - Acceptance mapping: AC-2
  - Exit criteria:
    - follow-up done

## AIDD:NEXT_3
- [ ] I0: stale pointer (ref: iteration_id=I0)
- [ ] I1: add core (ref: iteration_id=I1)
- [ ] review:F6: fix review (ref: id=review:F6)
- [ ] (none)

## AIDD:HANDOFF_INBOX
- [ ] Fix bug (id: review:F6) (Priority: high) (Blocking: true)
  - DoD: fix the bug

## AIDD:PROGRESS_LOG
- 2024-01-01 source=implement id=I1 kind=iteration hash=abc msg=done
