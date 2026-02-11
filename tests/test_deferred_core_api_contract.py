import os
import subprocess
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT
from aidd_runtime import tools_inventory


CORE_RUNTIME_ENTRYPOINTS = [
    "skills/aidd-init/runtime/init.py",
    "skills/researcher/runtime/research.py",
    "skills/aidd-flow-state/runtime/tasks_derive.py",
    "skills/aidd-docio/runtime/actions_apply.py",
    "skills/aidd-docio/runtime/context_expand.py",
]


class DeferredCoreApiContractTests(unittest.TestCase):
    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}".rstrip(":")
        return subprocess.run(
            ["python3", str(REPO_ROOT / script), *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_core_runtime_entrypoints_exist(self) -> None:
        for rel in CORE_RUNTIME_ENTRYPOINTS:
            with self.subTest(entrypoint=rel):
                path = REPO_ROOT / rel
                self.assertTrue(path.exists(), f"missing canonical entrypoint {rel}")

    def test_help_contract(self) -> None:
        for rel in CORE_RUNTIME_ENTRYPOINTS:
            with self.subTest(entrypoint=rel):
                result = self._run(rel, "--help")
                self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
                combined = f"{result.stdout}\n{result.stderr}".lower()
                self.assertIn("usage", combined, msg=f"{rel} must expose usage/help output")
                self.assertNotIn("redirect:", result.stderr.lower(), msg=f"{rel} must run as canonical entrypoint")

    def test_inventory_marks_canonical_core_entrypoints(self) -> None:
        payload = tools_inventory._build_payload(Path(REPO_ROOT))
        entries = {entry["path"]: entry for entry in payload.get("entrypoints", [])}
        for runtime_rel in CORE_RUNTIME_ENTRYPOINTS:
            with self.subTest(entrypoint=runtime_rel):
                self.assertIn(runtime_rel, entries, f"{runtime_rel} must be present in tools inventory")
                entry = entries[runtime_rel]
                self.assertIn(entry.get("classification"), {"canonical_stage", "shared_skill"})
                self.assertFalse(entry.get("migration_deferred", False))
                self.assertEqual(entry.get("runtime_classification"), "python_entrypoint")
                self.assertIn(
                    runtime_rel,
                    entry.get("python_owner_paths", []),
                    f"{runtime_rel} must resolve to itself in python owner paths",
                )


if __name__ == "__main__":
    unittest.main()
