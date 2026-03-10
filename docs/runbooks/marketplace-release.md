# Marketplace Release Runbook

This runbook defines the go/no-go checklist for public releases and official marketplace submission.

## 1) Local release readiness (must pass)

Run from repository root:

```bash
tests/repo_tools/release-readiness.sh
```

The script verifies:
- plugin/marketplace manifest version parity;
- plugin and marketplace manifest validation (`claude plugin validate`);
- dist surface integrity (`dist_manifest_check`);
- full repo checks (`ci-lint`, `smoke-workflow`).

## 2) Required repository settings

Apply in GitHub repository settings:

1. Set repository variable `AIDD_SECURITY_ENFORCE=1`.
2. Enable branch protection on `main` with required checks:
   - `lint-and-test`
   - `smoke-workflow`
   - `dist-check`
   - `dependency-review`
   - `security-secret-scan`
   - `security-sast`
3. Enable Secret Scanning and Push Protection.

## 3) Marketplace reference policy

Policy:
- Stable channel is tag-pinned only: `marketplace.json` root `plugins[].source.ref` must be `vX.Y.Z`.
- `main` must always keep the latest already-published stable tag (never an unreleased future tag).
- On tag builds, tag/version parity is mandatory (`tag == manifests version`).
- Legacy `stable_0.0.x` tags are historical prehistory only; official baseline starts from `v0.1.0`.

Guarded by:
- `tests/repo_tools/release_manifest_guard.py`
- `.github/workflows/release-governance.yml`

## 4) Release PR + tag workflow (stable self-hosted)

1. Create branch `release/vX.Y.Z` from `main`.
2. Update:
   - `.claude-plugin/plugin.json` -> `version: X.Y.Z`
   - `.claude-plugin/marketplace.json` -> `plugins[].version: X.Y.Z`, `source.ref: vX.Y.Z`
   - `.claude-plugin/official-submission.json` -> `plugin.version: X.Y.Z`
   - `CHANGELOG.md` -> release section `## vX.Y.Z (YYYY-MM-DD)`
3. Run:
   - `tests/repo_tools/release-readiness.sh`
4. Open and merge Release PR with all required checks green.
5. Create tag `vX.Y.Z` on merge commit and publish GitHub Release.
6. Validate clean install and init:
   - `/plugin marketplace add GrinRus/ai_driven_dev`
   - `/plugin install feature-dev-aidd@aidd-local`
   - `/feature-dev-aidd:aidd-init`

Rule between releases:
- Keep `marketplace.json` on the latest already-published stable tag.
- Never point root marketplace to unreleased commits.

## 5) Official Anthropic marketplace submission

Prepare metadata according to official rules and submit through:
- Directory repository:
  - [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
- Official submission form:
  - [Plugin directory submission form](https://clau.de/plugin-directory-submission)
- Official plugin docs:
  - [Claude Code plugins docs](https://code.claude.com/docs/en/plugins)
- Submission metadata bundle in this repo:
  - `.claude-plugin/official-submission.json`

Use this tracking issue title in your repo:
- `marketplace-submission`
Tracking issue (created): [#99](https://github.com/GrinRus/ai_driven_dev/issues/99)

Suggested issue body sections:
- Submission date
- Submitted metadata bundle
- Reviewer feedback
- Blocking items
- Follow-up PRs
- Approval date

## 6) Final go/no-go

- Validate install from clean environment:
  - `/plugin marketplace add GrinRus/ai_driven_dev`
  - `/plugin install feature-dev-aidd@aidd-local`
  - `/feature-dev-aidd:aidd-init`
- Validate upgrade path:
  - bump patch version;
  - update marketplace ref/version;
  - run `/plugin update <plugin>` and restart Claude Code.
