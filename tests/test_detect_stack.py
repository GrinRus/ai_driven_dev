import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


class DetectStackTests(unittest.TestCase):
    def make_tempdir(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="aidd-detect-stack-"))
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_detect_stack_json_output(self) -> None:
        root = self.make_tempdir()
        (root / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

        wrapper = REPO_ROOT / "tools" / "detect-stack.sh"
        proc = subprocess.run(
            [str(wrapper), "--format", "json", "--root", str(root)],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        payload = json.loads(proc.stdout)
        self.assertIn("node", payload.get("stack_hint", []))
        self.assertIn("python", payload.get("stack_hint", []))
        self.assertNotIn("enabled_skills", payload)

    def test_update_profile_merges_lists(self) -> None:
        root = self.make_tempdir()
        profile = root / "profile.md"
        template = REPO_ROOT / "templates" / "aidd" / "docs" / "architecture" / "profile.md"
        profile.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

        from tools import detect_stack

        updated = detect_stack.update_profile(
            profile,
            {"stack_hint": ["node"]},
        )
        self.assertTrue(updated)
        text = profile.read_text(encoding="utf-8")
        self.assertIn("- node", text)
        self.assertNotIn("enabled_skills", text)


if __name__ == "__main__":
    unittest.main()
