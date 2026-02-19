# Wave 102 Skill Inventory (All 19 Skills)

Status: completed
Wave: 102
Scope: `skills/*/SKILL.md`
Generated from repository state on branch `codex/wave-102`.

## Matrix

| Skill | Type | Frontmatter baseline (`name/description/lang/model/user-invocable`) | `## Command contracts` | `## Additional resources` (`when/why`) | Canonical runtime-path guidance | `Run subagent` wording | Key gaps (pre-wave) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `aidd-core` | shared | partial (no `allowed-tools`, baseline keys present) | missing | present (ok) | canonical | n/a | add compact command contracts |
| `aidd-docio` | shared | partial (baseline keys present) | missing | present (ok) | canonical | n/a | add compact command contracts |
| `aidd-flow-state` | shared | partial (baseline keys present) | missing | present (ok) | canonical | n/a | add compact command contracts |
| `aidd-loop` | shared | gap (`name` missing) | missing | present (missing `when/why`) | canonical | n/a | add `name`, contracts, normalize resources |
| `aidd-observability` | shared | partial (baseline keys present) | missing | present (ok) | canonical | n/a | add compact command contracts |
| `aidd-policy` | shared | partial (baseline keys present) | missing | present (ok) | canonical | n/a | add compact command contracts |
| `aidd-rlm` | shared | partial (baseline keys present) | missing | missing | canonical | n/a | add contracts + resources section |
| `aidd-stage-research` | shared | partial (baseline keys present) | missing | missing | canonical | n/a | add contracts + resources section |
| `aidd-init` | stage | gap (`name` missing) | present | present (ok) | canonical + anti-relative rule | no subagent | add `name`; stabilize runtime-path wording |
| `idea-new` | stage | mostly aligned (`name` present) | present | present (ok) | canonical | explicit (1) | wording alignment only |
| `researcher` | stage | gap (`name` missing) | present | present (ok) | canonical | explicit (1) | add `name`; wording alignment only |
| `plan-new` | stage | gap (`name` missing) | present | present (ok) | canonical | implicit | add `name`; align subagent wording |
| `review-spec` | stage | gap (`name` missing) | present | present (ok) | canonical | explicit (2) | add `name`; wording alignment only |
| `spec-interview` | stage | gap (`name` missing) | present | present (ok) | canonical | no subagent | add `name`; explicit no-fork note |
| `tasks-new` | stage | gap (`name` missing) | present | present (ok) | canonical | explicit (1) | add `name`; wording alignment only |
| `implement` | stage | gap (`name` missing) | present | present (ok) | canonical | explicit (1) | add `name`; add stable loop-policy markers |
| `review` | stage | gap (`name` missing) | present | present (ok) | canonical | explicit (1) | add `name`; add stable loop-policy markers |
| `qa` | stage | gap (`name` missing) | present | present (ok) | canonical | explicit (1) | add `name`; add stable loop-policy markers |
| `status` | stage | gap (`name` missing) | present | present (ok) | canonical | no subagent | add `name`; wording alignment only |

## Gap Summary (pre-wave)

1. Missing `name` frontmatter in 10 stage skills plus `aidd-loop`.
2. Shared skills lacked deterministic `Command contracts` structure (8/8 gaps).
3. `Additional resources` coverage in shared skills was incomplete (`aidd-rlm`, `aidd-stage-research`) and inconsistent (`aidd-loop` missing `when/why`).
4. Loop policy tests relied on brittle literal assertions, not semantic markers.
5. Lint checks were strong for stage skills but weak for shared skill contract sections.

## Rollout Priority

1. P0: Frontmatter `name` normalization + shared section hardening.
2. P0: Lint contract updates to enforce shared checks and deterministic diagnostics.
3. P0: Loop semantic markers + policy-test migration from exact text to semantic checks.
4. P0: Version/baseline sync and full regression (`ci-lint` + `smoke-workflow`).

## Wave 102 Release Checklist

- [x] W102-1 inventory finalized (this document).
- [x] W102-2 policy crosswalk documented.
- [x] W102-3 shared `Command contracts` normalized.
- [x] W102-4 shared `Additional resources` normalized.
- [x] W102-5 frontmatter `name` gaps closed.
- [x] W102-6 stage wording/subagent no-fork alignment complete.
- [x] W102-7 runtime-path canonicalization sweep complete.
- [x] W102-8 loop wrapper-policy semantic markers added.
- [x] W102-9 lint contract upgrades merged.
- [x] W102-10 semantic policy tests merged.
- [x] W102-11 versions/baseline synced.
- [x] W102-12 full regression and acceptance completed.
