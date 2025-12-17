---
description: "Build aidd/docs/tasklist/&lt;ticket&gt;.md for the feature"
argument-hint: "<TICKET>"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Read,Edit,Write,Grep,Glob
model: inherit
disable-model-invocation: false
---

## Context
`/tasks-new`converts the plan into a detailed checklist (`aidd/docs/tasklist/&lt;ticket&gt;.md`) across analytics, implementation, QA, release, and post-release stages.

## Input Artifacts
-`aidd/docs/plan/&lt;ticket&gt;.md`— source of iterations/DoD.
-`aidd/docs/prd/&lt;ticket&gt;.prd.md`+`## PRD Review`action items.
-`aidd/docs/research/&lt;ticket&gt;.md`.
-`templates/tasklist.md`/`claude-presets/feature-impl.yaml`for baseline structure.

## When to Run
- After`/plan-new`succeeds. Rerun when plan/PRD receives significant updates.

## Automation & Hooks
-`gate-workflow`requires tasklist entries before code edits.
-`feature-impl`preset can populate default sections for Wave 7 tasks.

## What is Edited
-`aidd/docs/tasklist/&lt;ticket&gt;.md`— front matter (Ticket, Slug hint, Feature, Status, PRD/Plan/Research links, Updated date) and sections 1–6 + “How to track progress”.

## Step-by-step Plan
1. Create/open`aidd/docs/tasklist/&lt;ticket&gt;.md`; copy from template if new.
2. Update front matter with current ticket info and date.
3. Migrate plan iterations into the relevant sections (analytics, build, QA, release, post-release).
4. Copy all approved action items from PRD Review into explicit checkboxes.
5. Add the “How to track progress” guide (change`- [ ] → - [x]`, include date/iteration/links).
6. Expand`feature-impl`preset if you need demo wave tasks.
7. Summarize top-priority checkboxes in your response and set`Checkbox updated: tasklist drafted`when ready.

## Fail-fast & Questions
- Missing plan or PRD — pause until earlier steps are complete.
- If owners or dependencies are unknown, ask before finalizing.

## Expected Output
- Updated`aidd/docs/tasklist/&lt;ticket&gt;.md`aligned with plan/PRD, including action items and progress instructions.
- Response lists key checkboxes to tackle first.

## CLI Examples
-`/tasks-new ABC-123`
-`!bash -lc 'claude-workflow preset feature-impl --ticket "ABC-123"'`
