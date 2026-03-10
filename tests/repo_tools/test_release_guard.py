from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "tests" / "repo_tools" / "release_guard.py"


def _write_fixture(root: Path, *, version: str, marketplace_version: str, ref: str) -> None:
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "feature-dev-aidd",
                "version": version,
            }
        ),
        encoding="utf-8",
    )
    (manifest_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "aidd-local",
                "plugins": [
                    {
                        "name": "feature-dev-aidd",
                        "source": {"source": "github", "repo": "GrinRus/ai_driven_dev", "ref": ref},
                        "version": marketplace_version,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class ReleaseGuardTests(unittest.TestCase):
    def _run(self, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GUARD), "--root", str(root), *extra],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_passes_when_versions_and_ref_are_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, version="0.1.0", marketplace_version="0.1.0", ref="v0.1.0")
            (root / "CHANGELOG.md").write_text("## Unreleased\n", encoding="utf-8")
            result = self._run(root)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_fails_when_marketplace_ref_is_not_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, version="0.1.0", marketplace_version="0.1.0", ref="main")
            (root / "CHANGELOG.md").write_text("## Unreleased\n", encoding="utf-8")
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source.ref", result.stderr)

    def test_fails_on_manifest_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, version="0.1.0", marketplace_version="0.1.1", ref="v0.1.0")
            (root / "CHANGELOG.md").write_text("## Unreleased\n", encoding="utf-8")
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("version mismatch", result.stderr)

    def test_fails_when_tag_does_not_match_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, version="0.1.0", marketplace_version="0.1.0", ref="v0.1.0")
            (root / "CHANGELOG.md").write_text("## Unreleased\n## 0.1.0 - 2026-03-10\n", encoding="utf-8")
            result = self._run(root, "--tag", "v0.1.1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tag mismatch", result.stderr)

    def test_fails_when_changelog_heading_is_missing_for_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root, version="0.1.0", marketplace_version="0.1.0", ref="v0.1.0")
            (root / "CHANGELOG.md").write_text("## Unreleased\n## 0.0.9 - 2026-03-01\n", encoding="utf-8")
            result = self._run(root, "--tag", "v0.1.0")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing release heading", result.stderr)


if __name__ == "__main__":
    unittest.main()
