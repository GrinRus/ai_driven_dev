---
description: "Build aidd/docs/tasklist/<ticket>.md for the feature"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.3
source_version: 1.0.3
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_stage.py:*)
model: inherit
disable-model-invocation: false
---

## Context
`/tasks-new` converts the plan into a detailed checklist (`aidd/docs/tasklist/<ticket>.md`) across analytics, implementation, QA, release, and post-release stages. Include any free-form notes after the ticket in the checklist context.

## Input Artifacts
- `aidd/docs/plan/<ticket>.md`— source of iterations/DoD.
- `aidd/docs/prd/<ticket>.prd.md`+`## PRD Review` action items.
- `aidd/docs/research/<ticket>.md`.
- `templates/tasklist.md`/`claude-presets/feature-impl.yaml` for baseline structure.

## When to Run
- After `/plan-new` succeeds. Rerun when plan/PRD receives significant updates.

## Automation & Hooks
- `gate-workflow` requires tasklist entries before code edits.
- `feature-impl` preset can populate default sections for Wave 7 tasks.
- `python3 tools/set_active_stage.py tasklist` records the `tasklist` stage.

## What is Edited
- `aidd/docs/tasklist/<ticket>.md`— front matter (Ticket, Slug hint, Feature, Status, PRD/Plan/Research links, Updated date) and sections 1–6 + “How to track progress”.

## Step-by-step Plan
1. Record the `tasklist` stage: `python3 tools/set_active_stage.py tasklist`.
2. Create/open `aidd/docs/tasklist/<ticket>.md`; copy from template if new.
3. Update front matter with current ticket info and date.
4. Migrate plan iterations into the relevant sections (analytics, build, QA, release, post-release).
5. Copy all approved action items from PRD Review into explicit checkboxes.
6. Add the “How to track progress” guide (change `- [ ] → - [x]`, include date/iteration/links).
7. Expand `feature-impl` preset if you need demo wave tasks.
8. Summarize top-priority checkboxes in your response and set `Checkbox updated: tasklist drafted` when ready.

## Fail-fast & Questions
- Missing plan or PRD — pause until earlier steps are complete.
- If owners or dependencies are unknown, ask before finalizing.

## Expected Output
- Updated `aidd/docs/tasklist/<ticket>.md` aligned with plan/PRD, including action items and progress instructions.
- Response lists key checkboxes to tackle first.

## CLI Examples
- `/tasks-new ABC-123`
- `!bash -lc 'claude-workflow preset feature-impl --ticket "ABC-123"'`
