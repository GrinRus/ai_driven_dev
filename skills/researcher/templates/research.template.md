# Research Summary — {{feature}}

Status: {{doc_status}}
Last reviewed: {{date}}
Commands:
  Research scan: python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket {{ticket}} --auto --paths {{paths}} --keywords {{keywords}}
Artifacts:
  PRD: aidd/docs/prd/{{ticket}}.prd.md
  Tasklist: aidd/docs/tasklist/{{ticket}}.md

## AIDD:CONTEXT_PACK
- {{summary_short}}
- Paths discovered: {{paths_discovered}}
- Invalid paths: {{invalid_paths}}

## AIDD:PRD_OVERRIDES
{{prd_overrides}}

## AIDD:NON_NEGOTIABLES
- {{non_negotiables}}

## AIDD:OPEN_QUESTIONS
- {{open_questions}}

## AIDD:RISKS
- {{risks}}

## AIDD:DECISIONS
- {{decisions}}

## AIDD:INTEGRATION_POINTS
- {{integration_points}}

## AIDD:REUSE_CANDIDATES
- {{reuse_candidates}}

## AIDD:COMMANDS_RUN
- {{commands_run}}

## AIDD:RLM_EVIDENCE
- Status: {{rlm_status}}
- Pack: {{rlm_pack_path}}
- Warnings: {{rlm_warnings}}
- Pending reason: {{rlm_pending_reason}}
- Next action: {{rlm_next_action}}
- Auto recovery: auto_recovery_attempted={{rlm_auto_recovery_attempted}}, bootstrap_attempted={{rlm_bootstrap_attempted}}, finalize_attempted={{rlm_finalize_attempted}}, recovery_path={{rlm_recovery_path}}
- Slice: python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket {{ticket}} --query "<token>"
- Nodes/links: {{rlm_nodes_path}} / {{rlm_links_path}}

## AIDD:TEST_HOOKS
- {{test_hooks}}
- Evidence: {{tests_evidence}}
- Suggested tasks: {{suggested_test_tasks}}

## Summary
- Goal: {{goal}}
- Scope: {{scope}}
- Inputs: {{inputs}}
- Entry points: {{entry_points}}
- Test pointers: {{test_pointers}}

## Notes
- Gaps: {{gap-description}}
- Next steps: {{next-step}}
- Additional notes: {{manual-note}}
