# Output Contract

Use the same output shape across agents/commands:

- `Status: ...`
- `Work item key: ...`
- `Artifacts updated: ...`
- `Tests: ...`
- `Blockers/Handoff: ...`
- `Next actions: ...`
- `AIDD:READ_LOG: ...`
- `AIDD:ACTIONS_LOG: ...`

Notes:
- Add `Checkbox updated: ...` when stage/agent contract requires it.
- In planning stages `AIDD:ACTIONS_LOG` may be `n/a`.
- In loop stages always include a concrete actions log path.
