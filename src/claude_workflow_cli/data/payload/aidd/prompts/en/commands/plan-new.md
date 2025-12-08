---
description: "Implementation plan + validation"
argument-hint: "<TICKET>"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Read,Edit,Write,Grep,Glob
model: inherit
disable-model-invocation: false
---

## Context
`/plan-new`transforms an approved PRD into`aidd/docs/plan/&lt;ticket&gt;.md`using the planner and validator agents. Run it before`/tasks-new`or any implementation work. The plan must include architecture & patterns (KISS/YAGNI/DRY/SOLID, default service layer + adapters/ports), reuse points from Researcher, and avoid over-engineering.

## Input Artifacts
-`aidd/docs/prd/&lt;ticket&gt;.prd.md`— READY with`## PRD Review`.
-`aidd/docs/research/&lt;ticket&gt;.md`— integration/risks.
- ADRs/backlog notes referenced by the PRD.

## When to Run
- Immediately after`/idea-new`/`/review-prd`.
- Repeat when the PRD changes materially and the plan must be updated.

## Automation & Hooks
- Planner agent writes`aidd/docs/plan/&lt;ticket&gt;.md`.
- Validator agent checks the plan and returns PASS/BLOCKED.
-`claude-presets/feature-plan.yaml`can prefill iterations for known waves.

## What is Edited
-`aidd/docs/plan/&lt;ticket&gt;.md`.
- “Open questions” sections in PRD/plan — action items from PRD Review must be synced.

## Step-by-step Plan
1. Verify PRD status = approved; otherwise run`/review-prd &lt;ticket&gt;`.
2. Call **planner** to generate the plan (Architecture & Patterns section: boundaries, chosen patterns, reuse points; iterations/DoD/references; minimal viable scope).
3. Invoke **validator**. If BLOCKED, collect questions, resolve them, rerun planner/validator.
4. Copy action items/open questions from PRD Review into the plan (and PRD’s section if needed).
5. Optionally expand`feature-plan`preset.

## Fail-fast & Questions
- Missing PRD/research — stop and request prerequisites.
- Unknown dependencies/integrations — ask before finalizing the plan.

## Expected Output
-`aidd/docs/plan/&lt;ticket&gt;.md`filled with Architecture & Patterns (boundaries/patterns/reuse, minimal viable scope), iterations, DoD, risks, metrics.
- Validator PASS; otherwise the list of blocking questions.

## CLI Examples
-`/plan-new ABC-123`
-`!bash -lc 'claude-workflow preset feature-plan --ticket "ABC-123"'`
