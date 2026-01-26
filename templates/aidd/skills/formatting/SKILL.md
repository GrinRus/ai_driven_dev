# SKILL: formatting

## Name
Formatting and linting

## Version
1.0

## When to use
- Any change that requires formatting or linting checks.

## Commands
### Format
- <formatter command from project>

### Lint
- <lint command from project>

## Evidence
- Save logs under: `aidd/reports/tests/<ticket>.<ts>.format.log`.
- In the response, include the log path and a 1-line summary.

## Pitfalls
- Avoid running format on generated files.
- Respect repo formatting rules and ignore lists.

## Tooling
- Prefer repo hooks if configured; avoid ad-hoc formatting when hooks handle it.
