---
name: aidd-policy
description: Shared policy contract for output format, read discipline, question format, and loop safety.
lang: en
model: inherit
user-invocable: false
---

## Scope
- This skill is the single source of truth for reusable policy guidance.
- Stage/runtime ownership stays in `feature-dev-aidd:aidd-core` and stage skills.
- Preload matrix v2: this skill is required for every subagent role.

## Output contract (required)
- Status: ...
- Work item key: ...
- Artifacts updated: ...
- Tests: ...
- Blockers/Handoff: ...
- Next actions: ...
- AIDD:READ_LOG: ...
- AIDD:ACTIONS_LOG: ...

Include `Checkbox updated: ...` when the command/stage contract expects it.

## Question format
Use this exact format when asking the user:

```text
Question N (Blocker|Clarification): ...
Why: ...
Options: A) ... B) ...
Default: ...
```

## Read policy (pack-first)
- Read packs/excerpts before full documents.
- Prefer `rlm_slice.py` and section slices for focused evidence.
- Full-file reads are allowed only when slices are insufficient.
- Keep `AIDD:READ_LOG` compact and point to `aidd/reports/**`.

## Loop safety
- `AIDD_SKIP_STAGE_WRAPPERS=1` is debug-only.
- In `strict` mode or stages `review|qa`, treat wrapper/preflight bypass as blocked (`wrappers_skipped_unsafe`).
- In `fast` mode on `implement`, bypass can warn (`wrappers_skipped_warn`) only for diagnostics.
- Missing preflight/readmap/writemap/actions/log artifacts is a contract violation.

## Runtime path safety
- Never guess runtime filenames/paths.
- Execute only runtime entrypoints explicitly listed in the current stage skill `Command contracts`.
- Use only canonical active-state runtime commands from the current stage contract; do not use deprecated aliases.
- For loop stages, do not invoke preflight runtime directly from stage prompt flow; preflight belongs to canonical wrapper orchestration only.
- If command output contains `can't open file .../skills/.../runtime/...`, stop and report BLOCKED (`runtime_path_missing_or_drift`) with evidence path.

## Retry safety
- Do not repeat the same failing shell command in a loop.
- For cwd/build-tool mismatch (`./gradlew` missing, or `does not contain a Gradle build`), allow at most one corrected attempt after explicit cwd resolution.
- If corrected attempt still fails, stop with blocker (`tests_cwd_mismatch`) and handoff instead of further retries.

## Subagent guard
- Subagents must not edit `aidd/docs/.active.json`.

## Additional resources
- [references/output-contract.md](references/output-contract.md) (when: response structure is unclear; why: copy exact contract fields and stage notes).
- [references/read-policy.md](references/read-policy.md) (when: deciding between slice and full read; why: keep evidence gathering deterministic and minimal).
- [references/question-format.md](references/question-format.md) (when: blockers require user clarification; why: ask short, actionable questions with defaults).
- [references/loop-safety.md](references/loop-safety.md) (when: loop-stage safety flags or artifacts are in question; why: apply consistent blocked/warn policy).
