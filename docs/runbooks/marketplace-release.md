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
- Integration PRs (non-release) keep `marketplace.json` on current published baseline (currently `main`).
- Official release PRs must switch `source.ref` to semver tag (`vX.Y.Z`).
- On tag builds, tag/version parity is mandatory (`tag == manifests version`).

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
- Do not create tags or publish GitHub Release in integration PRs.
- Keep release publish steps only in dedicated release PR.

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
