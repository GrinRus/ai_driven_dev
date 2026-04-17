import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import runtime


class RuntimeWriteSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_rejects_plugin_repo_as_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".git").mkdir(parents=True, exist_ok=True)
            (plugin_root / "aidd" / "docs").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)

            with self.assertRaises(RuntimeError):
                runtime.resolve_roots(plugin_root)

    def test_allows_plugin_workspace_with_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".git").mkdir(parents=True, exist_ok=True)
            (plugin_root / "aidd" / "docs").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            os.environ["AIDD_ALLOW_PLUGIN_WORKSPACE"] = "1"

            workspace_root, project_root = runtime.resolve_roots(plugin_root)
            self.assertEqual(workspace_root, plugin_root.resolve())
            self.assertEqual(project_root, (plugin_root / "aidd").resolve())

    def test_prefers_explicit_workspace_target_over_plugin_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            workspace = Path(tmpdir) / "workspace"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".git").mkdir(parents=True, exist_ok=True)
            (workspace / ".git").mkdir(parents=True, exist_ok=True)
            (workspace / "aidd" / "docs").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)

            workspace_root, project_root = runtime.resolve_roots(workspace)
            self.assertEqual(workspace_root, workspace.resolve())
            self.assertEqual(project_root, (workspace / "aidd").resolve())

    def test_rejects_plugin_root_pointing_to_skills_subdir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-guard-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / "skills").mkdir(parents=True, exist_ok=True)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root / "skills")

            with self.assertRaisesRegex(RuntimeError, "must point to plugin root"):
                runtime.require_plugin_root()

    def test_resolve_plugin_root_with_fallback_from_runtime_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-plugin-fallback-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            runtime_file = plugin_root / "skills" / "aidd-loop" / "runtime" / "loop_run.py"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            runtime_file.parent.mkdir(parents=True, exist_ok=True)
            runtime_file.write_text("# fallback probe\n", encoding="utf-8")
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            os.environ.pop("AIDD_PLUGIN_DIR", None)
            os.environ.pop("PYTHONPATH", None)

            resolved = runtime.resolve_plugin_root_with_fallback(start_file=runtime_file)

            self.assertEqual(resolved, plugin_root.resolve())
            self.assertEqual(os.environ.get("CLAUDE_PLUGIN_ROOT"), str(plugin_root.resolve()))
            self.assertEqual(os.environ.get("PYTHONPATH"), str(plugin_root.resolve()))

    def test_resolve_plugin_root_with_fallback_raises_when_unresolvable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-plugin-fallback-") as tmpdir:
            random_file = Path(tmpdir) / "not_plugin" / "skills" / "aidd-loop" / "runtime" / "loop_run.py"
            random_file.parent.mkdir(parents=True, exist_ok=True)
            random_file.write_text("# no plugin markers\n", encoding="utf-8")
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            os.environ.pop("AIDD_PLUGIN_DIR", None)

            with self.assertRaisesRegex(RuntimeError, "CLAUDE_PLUGIN_ROOT"):
                runtime.resolve_plugin_root_with_fallback(start_file=random_file)

    def _init_git_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Runtime Safety"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "runtime-safety@example.com"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)

    def test_plugin_write_safety_snapshot_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            self._init_git_repo(plugin_root)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            self.assertTrue(snapshot.get("enabled"))
            self.assertTrue(snapshot.get("supported"))

            (plugin_root / "runtime_mutation.txt").write_text("mutation\n", encoding="utf-8")
            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertFalse(ok)
            self.assertIn("plugin_write_safety_violation", message)
            self.assertIn("runtime_mutation.txt", message)

    def test_plugin_write_safety_detects_mutation_when_status_shape_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            tracked_file = plugin_root / "tracked.txt"
            tracked_file.write_text("v1\n", encoding="utf-8")
            self._init_git_repo(plugin_root)
            tracked_file.write_text("v2\n", encoding="utf-8")

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            self.assertTrue(snapshot.get("supported"))

            tracked_file.write_text("v3\n", encoding="utf-8")
            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertFalse(ok)
            self.assertIn("plugin_write_safety_violation", message)
            self.assertIn("content_changed_without_status_delta=1", message)

    def test_plugin_write_safety_snapshot_passes_when_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            self._init_git_repo(plugin_root)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertTrue(ok, msg=message)

    def test_plugin_write_safety_ignores_python_bytecode_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            self._init_git_repo(plugin_root)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            pycache_dir = plugin_root / "skills" / "__pycache__"
            pycache_dir.mkdir(parents=True, exist_ok=True)
            (pycache_dir / "module.cpython-310.pyc").write_bytes(b"pyc")

            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertTrue(ok, msg=message)

    def test_plugin_write_safety_ignores_pytest_cache_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            self._init_git_repo(plugin_root)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            pytest_cache = plugin_root / ".pytest_cache" / "v" / "cache"
            pytest_cache.mkdir(parents=True, exist_ok=True)
            (pytest_cache / "nodeids").write_text("[]\n", encoding="utf-8")

            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertTrue(ok, msg=message)

    def test_plugin_write_safety_ignores_coverage_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            self._init_git_repo(plugin_root)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            (plugin_root / ".coverage").write_text("data\n", encoding="utf-8")
            (plugin_root / ".coverage.worker-1").write_text("data\n", encoding="utf-8")

            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertTrue(ok, msg=message)

    def test_plugin_write_safety_override_disables_guard(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            self._init_git_repo(plugin_root)

            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            os.environ["AIDD_ALLOW_PLUGIN_WRITES"] = "1"
            snapshot = runtime.capture_plugin_write_safety_snapshot()
            self.assertFalse(snapshot.get("enabled"))
            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertTrue(ok, msg=message)

    def test_plugin_write_safety_unavailable_defaults_to_warn_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)

            snapshot = runtime.capture_plugin_write_safety_snapshot()
            self.assertTrue(snapshot.get("enabled"))
            self.assertFalse(snapshot.get("supported"))

            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertTrue(ok)
            self.assertIn("plugin_write_safety_unavailable", message)

    def test_plugin_write_safety_missing_plugin_root_defaults_to_warn_mode(self) -> None:
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        os.environ.pop("AIDD_PLUGIN_DIR", None)

        snapshot = runtime.capture_plugin_write_safety_snapshot()
        self.assertTrue(snapshot.get("enabled"))
        self.assertFalse(snapshot.get("supported"))
        self.assertEqual(str(snapshot.get("plugin_root") or ""), "")

        ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
        self.assertTrue(ok)
        self.assertIn("plugin_write_safety_unavailable", message)

    def test_plugin_write_safety_unavailable_strict_mode_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-write-safety-") as tmpdir:
            plugin_root = Path(tmpdir) / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            os.environ["AIDD_PLUGIN_WRITE_SAFETY_STRICT"] = "1"

            snapshot = runtime.capture_plugin_write_safety_snapshot()
            ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
            self.assertFalse(ok)
            self.assertIn("plugin_write_safety_unavailable", message)

    def test_plugin_write_safety_missing_plugin_root_strict_mode_blocks(self) -> None:
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        os.environ.pop("AIDD_PLUGIN_DIR", None)
        os.environ["AIDD_PLUGIN_WRITE_SAFETY_STRICT"] = "1"

        snapshot = runtime.capture_plugin_write_safety_snapshot()
        ok, message = runtime.verify_plugin_write_safety_snapshot(snapshot, source="unit-test")
        self.assertFalse(ok)
        self.assertIn("plugin_write_safety_unavailable", message)


if __name__ == "__main__":
    unittest.main()
