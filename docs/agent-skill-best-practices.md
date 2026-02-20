# Cross-Agent SKILL Authoring Best Practices

This guide defines a single SKILL authoring contract for repositories that are used with Claude Code, Codex, Cursor, and GitHub Copilot.

## Goals
- Keep instructions short enough to load quickly.
- Keep behavior deterministic through explicit command contracts.
- Keep deep implementation detail out of `SKILL.md` and in supporting files.
- Keep instructions portable across coding agents.

## Shared principles (portable across agents)
- Prefer concise, scoped instructions over long narrative text.
- Use progressive disclosure: top-level policy in `SKILL.md`, deep details in linked `references/*` or templates.
- Define exact command interfaces (inputs, outputs, failure modes), not implementation retells.
- Make instruction precedence explicit (repo-level policy first, then stage/task specifics).
- Keep references actionable: each link must say when to open it and why.

## Canonical SKILL structure in this repo
Use this structure for user-invocable stage skills.

1. Frontmatter: owner metadata, semver, `allowed-tools`, canonical Python entrypoint.
2. `## Steps`: short orchestration sequence.
3. `## Command contracts`: card(s) for critical command surfaces.
4. `## Notes`: strict policy exceptions only.
5. `## Additional resources`: optional deep dives with explicit trigger conditions.

## Command contract card format
Each critical command card must document interface behavior only.

```md
### `<command-or-entrypoint>`
- When to run: ...
- Inputs: ...
- Outputs: ...
- Failure mode: ...
- Next action: ...
```

Required card coverage:
- Every stage skill: canonical Python entrypoint in `skills/<stage>/runtime/*.py`.
- Loop stages (`implement`, `review`, `qa`): preflight + postflight contracts.

## Progressive disclosure policy
- Keep `SKILL.md` compact; move details to supporting files.
- Keep large examples, troubleshooting playbooks, and full command matrices in `references/*`.
- In `Additional resources`, every bullet must include:
  - `when:` the trigger to consult the file.
  - `why:` the expected decision/outcome after reading.

## Agent prompt topology rules (repo policy)
- Stage skills own orchestration: `skills/<stage>/SKILL.md` defines slash-stage routing and `Run subagent` flow.
- Agent prompts stay role-scoped: inputs, scope boundaries, evidence expectations, and handoff behavior only.
- Agents must not include own slash-stage self-links (`/feature-dev-aidd:<own-stage>`).
- Cross-stage handoff links are allowed when they point to the next stage and do not duplicate self orchestration.
- Do not duplicate stage runtime/manual-recovery guardrails in agents; keep those rules in stage `SKILL.md`.

## Cross-agent alignment notes
- Claude Code: skills are loaded on demand; keep descriptions precise and avoid oversized skills.
- Codex: repo instructions are layered through `AGENTS.md`; keep rules explicit and scoped.
- Cursor: use narrowly scoped rules and avoid broad global instructions.
- Copilot: repository custom instructions should stay short, self-contained, and directly actionable.

## Source map (official docs)
- Claude Code subagents: <https://docs.claude.com/en/docs/claude-code/sub-agents>
- Claude Code skills overview: <https://docs.claude.com/en/docs/claude-code/skills>
- Claude Code create skills (best practices): <https://docs.claude.com/en/docs/claude-code/skills/create-skills>
- OpenAI Codex AGENTS guide: <https://developers.openai.com/codex/agents>
- OpenAI Codex skills guide: <https://developers.openai.com/codex/skills>
- Cursor rules docs: <https://docs.cursor.com/context/rules>
- Cursor skills announcement + usage patterns: <https://cursor.com/blog/skills>
- GitHub Copilot repository custom instructions: <https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions?tool=visualstudio>
