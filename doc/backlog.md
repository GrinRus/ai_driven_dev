# Product Backlog

## Wave 1

- [ ] Harden CLI arguments in `init-claude-workflow.sh`  
  - [ ] Reject unsupported `--commit-mode` values with a descriptive error  
  - [ ] Add unit-style bash tests for argument parsing edge cases
- [ ] Unify README source of truth  
  - [ ] Extract shared content into a template consumed by both the repo and installer  
  - [ ] Add a validation step that prevents divergence between generated and canonical docs
- [ ] Make selective test hook configurable  
  - [ ] Introduce an environment flag to toggle strict failure behavior  
  - [ ] Document strict-mode usage in README and CLAUDE guidance
- [ ] Create smoke-test automation  
  - [ ] Provision a CI workflow that runs the installer in a throwaway repo  
  - [ ] Assert presence of critical files and successful Gradle task stubs
