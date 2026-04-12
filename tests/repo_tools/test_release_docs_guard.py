from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "tests" / "repo_tools" / "release_docs_guard.py"

MANIFEST = """\
public_release_docs:
  - README.md
  - README.en.md
  - CHANGELOG.md
  - SECURITY.md
  - SUPPORT.md
  - CONTRIBUTING.md
  - CODE_OF_CONDUCT.md

runtime_contract_docs:
  - agents/*.md
  - skills/*/SKILL.md
  - skills/*/templates/*.md

internal_dev_docs:
  - AGENTS.md
  - docs/backlog.md
  - docs/agent-skill-best-practices.md
  - docs/skill-language.md
  - docs/skill-trigger-taxonomy.md
  - docs/memory-v2-rfc.md
  - docs/runbooks/*.md
  - docs/revision/*.md
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_valid_fixture(root: Path) -> None:
    _write(root / "docs" / "release-docs-manifest.yaml", MANIFEST)
    _write(
        root / "README.md",
        """# README

## Документация
### Public docs
- `README.md`
- `README.en.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `SUPPORT.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
""",
    )
    _write(
        root / "README.en.md",
        """# README EN

## Documentation
### Public docs
- `README.md`
- `README.en.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `SUPPORT.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
""",
    )
    _write(
        root / "CHANGELOG.md",
        """# Release Notes

## Unreleased
- No user-facing changes yet.

## 0.1.0 - 2026-03-10
- First public release.
""",
    )

    for name in ("SECURITY.md", "SUPPORT.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"):
        _write(root / name, f"# {name}\n")

    _write(root / "agents" / "demo.md", "# Demo agent\n")
    _write(root / "skills" / "demo" / "SKILL.md", "# Demo skill\n")
    _write(root / "skills" / "demo" / "templates" / "template.md", "# Template\n")

    marker_block = (
        "> INTERNAL/DEV-ONLY\n\n"
        "Owner: feature-dev-aidd\n"
        "Last reviewed: 2026-04-12\n"
        "Status: active\n"
    )
    _write(root / "AGENTS.md", f"# AGENTS\n{marker_block}")
    _write(root / "docs" / "backlog.md", f"# Backlog\n{marker_block}")
    _write(root / "docs" / "agent-skill-best-practices.md", f"# Doc\n{marker_block}")
    _write(root / "docs" / "skill-language.md", f"# Doc\n{marker_block}")
    _write(root / "docs" / "skill-trigger-taxonomy.md", f"# Doc\n{marker_block}")
    _write(root / "docs" / "memory-v2-rfc.md", f"# Doc\n{marker_block}")
    _write(root / "docs" / "runbooks" / "tst001-audit-hardening.md", f"# Doc\n{marker_block}")
    _write(root / "docs" / "revision" / "repo-revision.md", f"# Doc\n{marker_block}")


class ReleaseDocsGuardTests(unittest.TestCase):
    def _run(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GUARD), "--root", str(root)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_passes_with_valid_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_valid_fixture(root)
            result = self._run(root)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_fails_when_internal_marker_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_valid_fixture(root)
            _write(root / "AGENTS.md", "# AGENTS\n")
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing `INTERNAL/DEV-ONLY` marker", result.stderr)

    def test_fails_when_internal_lifecycle_metadata_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_valid_fixture(root)
            _write(root / "AGENTS.md", "# AGENTS\n> INTERNAL/DEV-ONLY\n")
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing `Owner:` lifecycle marker", result.stderr)

    def test_fails_when_internal_doc_is_in_public_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_valid_fixture(root)
            _write(
                root / "README.md",
                """# README

## Документация
### Public docs
- `AGENTS.md`
""",
            )
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not appear in public README", result.stderr)

    def test_fails_when_internal_subsection_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_valid_fixture(root)
            _write(
                root / "README.en.md",
                """# README EN

## Documentation
### Public docs
- `README.md`
- `README.en.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `SUPPORT.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`

### Internal/Maintainer docs
- `AGENTS.md`
""",
            )
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subsection is forbidden in public-only README", result.stderr)

    def test_fails_when_changelog_uses_h3_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_valid_fixture(root)
            _write(
                root / "CHANGELOG.md",
                """# Release Notes
## Unreleased
### Breaking Changes
- test
""",
            )
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not use H3 sections", result.stderr)


if __name__ == "__main__":
    unittest.main()
