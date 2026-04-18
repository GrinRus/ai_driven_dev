import tempfile
import unittest
from pathlib import Path

from tests.repo_tools import prompt_template_sync


class PromptTemplateSyncTests(unittest.TestCase):
    def test_sync_guard_detects_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prompt-sync-") as tmpdir:
            root = Path(tmpdir)
            src = root / "skills" / "aidd-core" / "templates" / "workspace-agents.md"
            dst = root / "aidd" / "AGENTS.md"
            src.parent.mkdir(parents=True, exist_ok=True)
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("hello\n", encoding="utf-8")
            dst.write_text("hello\n", encoding="utf-8")

            result_ok = prompt_template_sync.main(["--root", str(root)])
            self.assertEqual(result_ok, 0)

            dst.write_text("changed\n", encoding="utf-8")
            result_fail = prompt_template_sync.main(["--root", str(root)])
            self.assertNotEqual(result_fail, 0)


if __name__ == "__main__":
    unittest.main()
