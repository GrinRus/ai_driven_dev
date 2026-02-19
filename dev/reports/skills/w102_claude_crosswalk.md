# Wave 102 Claude Crosswalk

Status: completed
Wave: 102
Purpose: map official Claude Skills guidance to repository policy/lint contracts.

## Source References

- [Claude Skills Overview](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Claude Skills Best Practices](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices)
- [Claude Skill Format](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/skill-format)
- [Claude Subagents](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/subagents)
- [Complete Guide to Building Skills for Claude](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf?hsLang=en)

## Crosswalk Matrix

| Official guidance area | Repo policy decision | Enforcement point |
| --- | --- | --- |
| Keep skills concise and interface-oriented | `SKILL.md` stays compact; implementation detail goes to `references/*`, `templates/*`, runtime docstrings | `AGENTS.md` SKILL authoring policy + size checks in `tests/repo_tools/lint-prompts.py` |
| Use explicit command interface contracts | Both stage and shared skills require `## Command contracts` with `When to run/Inputs/Outputs/Failure mode/Next action` | `tests/repo_tools/lint-prompts.py` + `tests/test_prompt_lint.py` |
| Progressive disclosure for supporting docs | Every skill has `## Additional resources` bullets with explicit `when:` and `why:` | `tests/repo_tools/lint-prompts.py` + `tests/test_prompt_lint.py` |
| Clear metadata and stable frontmatter | All skills require deterministic baseline keys; `name` must match skill directory | `tests/repo_tools/lint-prompts.py` |
| Subagent orchestration should be explicit | Stage skills use explicit `Run subagent ...` semantics where orchestration exists; `context/agent` frontmatter is forbidden in stage skills | `tests/repo_tools/lint-prompts.py` + `tests/test_prompt_lint.py` |
| Avoid ambiguous execution paths | Canonical runtime paths are `${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`; relative `python3 skills/...` guidance is forbidden | `tests/repo_tools/lint-prompts.py` + `tests/test_prompt_lint.py` |
| Policy checks should tolerate copy edits | Loop-policy tests validate semantic markers instead of exact literal prose | `tests/test_manual_preflight_policy.py` |

## No-fork / Subagent Policy Decision

- Stage skills in this repo intentionally **forbid** `context: fork` and `agent:` frontmatter delegation patterns.
- Reason: stage commands are user-facing orchestrators with strict runtime contracts, deterministic wrappers, and gate integration.
- Allowed model: explicit step-level `Run subagent ...` orchestration with no implicit fork context.
- Shared skills remain preload-only references and do not define user-facing stage orchestration.

## Planned Lint/Policy Changes in Wave 102

1. Extend lint checks for shared-skill contract sections and deterministic resources markers.
2. Enforce mandatory `name` key on every skill frontmatter.
3. Keep stage no-fork invariant checks (`Run subagent` count, forbidden fork phrases, no `context`/`agent` fields).
4. Replace brittle literal loop-policy assertions with semantic marker checks.

## Change Log (Wave 102 policy)

- Added shared-skill parity with stage skills for contract/resource sections.
- Tightened frontmatter baseline consistency (`name` required across all skills).
- Stabilized loop policy test semantics with explicit tags/markers.
- Preserved canonical runtime-path and no-fork stage contracts.
