from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.repo_tools import docs_parity_guard


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class DocsParityGuardTests(unittest.TestCase):
    def test_relative_link_with_fragment_is_not_reported_as_broken(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docs-parity-fragment-") as tmpdir:
            root = Path(tmpdir)
            doc = root / "docs" / "a.md"
            target = root / "docs" / "b.md"
            _write(doc, "[b section](b.md#sec)\n")
            _write(target, "## sec\n")

            errors: list[str] = []
            docs_parity_guard._check_relative_links(doc, errors)
            self.assertEqual(errors, [])

    def test_relative_link_with_query_is_not_reported_as_broken(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docs-parity-query-") as tmpdir:
            root = Path(tmpdir)
            doc = root / "docs" / "a.md"
            target = root / "docs" / "guide.md"
            _write(doc, "[guide plain](guide.md?plain=1)\n")
            _write(target, "# guide\n")

            errors: list[str] = []
            docs_parity_guard._check_relative_links(doc, errors)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
