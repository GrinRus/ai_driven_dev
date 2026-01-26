# SKILL: testing-node

## Name
Node.js testing

## Version
1.0

## When to use
- Project has `package.json` and runs tests via npm/pnpm/yarn.

## Commands
### Install
- npm install
- pnpm install
- yarn install

### Test (fast/targeted/full)
- npm test
- pnpm test
- yarn test
- npm test -- <pattern>

### Lint/Format
- npm run lint
- npm run format

## Evidence
- Save logs under: `aidd/reports/tests/<ticket>.<ts>.node.log`.
- In the response, include the log path and a 1-line summary.

## Pitfalls
- Keep lockfiles consistent with the chosen package manager.
- Watch out for scripts that trigger full suites by default.

## Tooling
- Use AIDD hooks for format/test cadence when enabled.
