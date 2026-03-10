## Summary

- What changed:
- Why:

## Validation

- [ ] `tests/repo_tools/ci-lint.sh`
- [ ] `tests/repo_tools/smoke-workflow.sh` (required for runtime/path changes)
- [ ] `python3 tests/repo_tools/dist_manifest_check.py --root .`
- [ ] `claude plugin validate .`

## Security and supply chain

- [ ] No new secrets/tokens in code or docs
- [ ] Dependencies/actions changes reviewed
- [ ] Security impact assessed

## Release and docs

- [ ] Updated `CHANGELOG.md` (`Unreleased`)
- [ ] Updated `README.md` + `README.en.md` if behavior changed
- [ ] Updated `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` versions if user-facing changes were made
