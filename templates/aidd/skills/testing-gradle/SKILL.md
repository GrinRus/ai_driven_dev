# SKILL: testing-gradle

## Name
Gradle testing

## Version
1.0

## When to use
- Project uses Gradle (`build.gradle` or `build.gradle.kts`).
- Tests are executed via Gradle tasks.

## Commands
### Install
- ./gradlew --version

### Test (fast/targeted/full)
- ./gradlew test
- ./gradlew :module:test
- ./gradlew test --tests "com.example.ClassNameTest"

### Lint/Format
- ./gradlew spotlessApply
- ./gradlew ktlintFormat

## Evidence
- Save logs under: `aidd/reports/tests/<ticket>.<ts>.gradle.log`.
- In the response, include the log path and a 1-line summary.

## Pitfalls
- Large multi-module builds can be slow; prefer targeted tasks.
- Keep JVM memory settings consistent with CI.

## Tooling
- Use AIDD hooks for format/test cadence when enabled.
