import os
import subprocess
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT
from tools import tools_inventory


DEFERRED_CORE_ENTRYPOINTS = [
    "tools/init.sh",
    "tools/research.sh",
    "tools/tasks-derive.sh",
    "tools/actions-apply.sh",
    "tools/context-expand.sh",
]


class DeferredCoreApiContractTests(unittest.TestCase):
    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        return subprocess.run(
            [str(REPO_ROOT / script), *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_deferred_core_entrypoints_exist_and_executable(self) -> None:
        for rel in DEFERRED_CORE_ENTRYPOINTS:
            with self.subTest(entrypoint=rel):
                path = REPO_ROOT / rel
                self.assertTrue(path.exists(), f"missing deferred-core entrypoint {rel}")
                self.assertTrue(os.access(path, os.X_OK), f"deferred-core entrypoint must be executable: {rel}")

    def test_help_contract(self) -> None:
        for rel in DEFERRED_CORE_ENTRYPOINTS:
            with self.subTest(entrypoint=rel):
                result = self._run(rel, "--help")
                self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
                combined = f"{result.stdout}\n{result.stderr}".lower()
                self.assertIn("usage", combined, msg=f"{rel} must expose usage/help output")

    def test_research_shim_emits_deprecation(self) -> None:
        result = self._run("tools/research.sh", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("DEPRECATED", result.stderr)

    def test_inventory_marks_deferred_core(self) -> None:
        payload = tools_inventory._build_payload(Path(REPO_ROOT))
        entries = {entry["path"]: entry for entry in payload.get("entrypoints", [])}
        for rel in DEFERRED_CORE_ENTRYPOINTS:
            with self.subTest(entrypoint=rel):
                self.assertIn(rel, entries, f"{rel} must be present in tools inventory")
                entry = entries[rel]
                self.assertEqual(entry.get("classification"), "core_api_deferred")
                self.assertTrue(entry.get("core_api"))
                self.assertTrue(entry.get("migration_deferred"))


if __name__ == "__main__":
    unittest.main()
