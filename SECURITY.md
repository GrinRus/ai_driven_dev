# Security Policy

## Supported Versions

Поддерживается только актуальная release-линия репозитория.
Исторические и неактуальные сборки считаются неподдерживаемыми.

## Reporting a Vulnerability

- Preferred: GitHub Security Advisory (private report).
- Fallback: open an issue only if the report is non-sensitive.
- Do not disclose exploit details publicly before a fix is available.

## Response Targets

- Initial acknowledgment: within 72 hours.
- Triage/update: within 14 calendar days.
- Fix timeline depends on severity and complexity; high/critical issues are prioritized.

## Scope

In scope:
- Plugin manifests and marketplace metadata.
- Runtime/hook code under `skills/` and `hooks/`.
- CI/release workflow integrity.

Out of scope:
- Vulnerabilities in third-party services outside this repository.
- Misconfiguration in private/local user environments.
