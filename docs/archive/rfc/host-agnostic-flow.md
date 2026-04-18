# RFC: Host-Agnostic AIDD Flow

> INTERNAL/DEV-ONLY: archived roadmap draft; not part of current runtime or release onboarding.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: historical
RFC status: Draft on hold
Updated: 2026-04-18

## Summary

This document stays in the repo only as a compact reminder of a deferred idea:
separate AIDD flow contracts from host-specific execution glue so the same stage
logic can run on Claude, Pi, or generic agent hosts.

## Why it is archived

- The current repository still treats Claude-oriented runtime, hooks, and file
  contracts as the canonical execution model.
- There is no approved implementation wave, owner-confirmed scope, or active CI
  contract for a host-agnostic engine split.
- Keeping a long pseudo-design here created more noise than guidance.

## Minimal design intent worth preserving

- Keep stage semantics contract-first and file-based.
- Keep adapters thin; do not bury business rules inside host integration glue.
- Prefer parity tests over host-specific prompt drift.
- Preserve current public slash commands and canonical report paths during any
  future migration.

## If this work is reopened

Reopen only with explicit owner confirmation and a concrete migration wave that
names:

- the target host surfaces;
- the adapter capability model;
- the conformance test plan;
- the compatibility strategy for existing hooks, stage commands, and reports.

Until then, this file is roadmap residue, not active architecture guidance.
