# RFC: Memory v2 for AIDD

> INTERNAL/DEV-ONLY: archived roadmap draft; not part of current runtime or release onboarding.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: historical
RFC status: Draft on hold
Updated: 2026-04-18

## Summary

This file remains only as a short record of a deferred idea: add a compact
memory layer on top of existing `aidd/docs/**` and `aidd/reports/**` artifacts
without replacing RLM evidence or loop-stage contracts.

## Why it is archived

- Current runtime does not ship `aidd-memory` entrypoints or memory-specific
  stage gates.
- The repository already has enough active complexity; a new memory subsystem
  without an approved rollout would add more moving parts than value.
- The previous long RFC mostly described hypothetical files and hooks that do
  not exist today.

## Minimal intent worth preserving

- If memory work is reopened, keep it pack-first, file-based, and deterministic.
- Treat RLM artifacts as code-evidence canon; any memory layer must stay
  secondary and compact.
- Do not add hard gates until there is real evidence that the layer improves
  stage quality.

## Reopen conditions

Proceed only with explicit owner confirmation and a concrete wave that names:

- the exact artifacts to generate;
- the runtime entrypoints to own them;
- the budget and schema limits;
- the tests proving that memory adds signal instead of repo bloat.

Until then, this file is archived roadmap context only.
