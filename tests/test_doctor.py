import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aidd_runtime import doctor


def _seed_project(root: Path) -> Path:
    project_root = root / "aidd"
    (project_root / "docs" / "shared").mkdir(parents=True, exist_ok=True)
    (project_root / "docs" / "loops").mkdir(parents=True, exist_ok=True)
    (project_root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
    (project_root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (project_root / "docs" / "shared" / "stage-lexicon.md").write_text("# stage\n", encoding="utf-8")
    (project_root / "docs" / "loops" / "template.loop-pack.md").write_text("# loop\n", encoding="utf-8")
    (project_root / "docs" / "tasklist" / "template.md").write_text("# tasklist\n", encoding="utf-8")
    return project_root


class DoctorAstIndexTests(unittest.TestCase):
    def test_optional_ast_index_does_not_fail_doctor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doctor-optional-") as tmpdir:
            workspace_root = Path(tmpdir)
            project_root = _seed_project(workspace_root)
            plugin_root = workspace_root / "plugin"
            for name in ("commands", "agents", "hooks", "tools", "templates"):
                (plugin_root / name).mkdir(parents=True, exist_ok=True)

            with mock.patch.object(doctor.runtime, "require_plugin_root", return_value=plugin_root):
                with mock.patch.object(
                    doctor.runtime,
                    "capture_plugin_write_safety_snapshot",
                    return_value={"enabled": False, "supported": True, "entries": []},
                ):
                    with mock.patch.object(doctor, "resolve_project_root", return_value=(workspace_root, project_root)):
                        with mock.patch.object(doctor, "_check_binary", return_value=(True, "/usr/bin/mock")):
                            with mock.patch.object(doctor, "_check_loop_observability", return_value=(True, "ok")):
                                with mock.patch.object(
                                    doctor.ast_index,
                                    "probe_readiness",
                                    return_value={
                                        "mode": "auto",
                                        "required": False,
                                        "available": False,
                                        "index_ready": False,
                                        "reason_code": "ast_index_binary_missing",
                                        "binary": "ast-index",
                                        "version": "",
                                    },
                                ):
                                    out = io.StringIO()
                                    err = io.StringIO()
                                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                                        rc = doctor.main([])
            self.assertEqual(rc, 0)
            self.assertIn("ast-index readiness", out.getvalue())

    def test_required_ast_index_blocks_doctor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doctor-required-") as tmpdir:
            workspace_root = Path(tmpdir)
            project_root = _seed_project(workspace_root)
            plugin_root = workspace_root / "plugin"
            for name in ("commands", "agents", "hooks", "tools", "templates"):
                (plugin_root / name).mkdir(parents=True, exist_ok=True)

            with mock.patch.object(doctor.runtime, "require_plugin_root", return_value=plugin_root):
                with mock.patch.object(
                    doctor.runtime,
                    "capture_plugin_write_safety_snapshot",
                    return_value={"enabled": False, "supported": True, "entries": []},
                ):
                    with mock.patch.object(doctor, "resolve_project_root", return_value=(workspace_root, project_root)):
                        with mock.patch.object(doctor, "_check_binary", return_value=(True, "/usr/bin/mock")):
                            with mock.patch.object(doctor, "_check_loop_observability", return_value=(True, "ok")):
                                with mock.patch.object(
                                    doctor.ast_index,
                                    "probe_readiness",
                                    return_value={
                                        "mode": "required",
                                        "required": True,
                                        "available": True,
                                        "index_ready": False,
                                        "reason_code": "ast_index_index_missing",
                                        "binary": "ast-index",
                                        "version": "ast-index 0.0.1",
                                    },
                                ):
                                    out = io.StringIO()
                                    err = io.StringIO()
                                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                                        rc = doctor.main([])
            self.assertEqual(rc, 1)
            self.assertIn("ast-index readiness", out.getvalue())
            self.assertIn("ast-index is required by config but not ready", out.getvalue())

    def test_ast_rollout_wave2_advisory_missing_metrics_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doctor-rollout-advisory-") as tmpdir:
            workspace_root = Path(tmpdir)
            project_root = _seed_project(workspace_root)
            plugin_root = workspace_root / "plugin"
            for name in ("commands", "agents", "hooks", "tools", "templates"):
                (plugin_root / name).mkdir(parents=True, exist_ok=True)

            gates_payload = {
                "ast_index": {
                    "rollout_wave2": {
                        "enabled": True,
                        "decision_mode": "advisory",
                        "scopes": ["implement", "review", "qa"],
                        "metrics_artifact": "aidd/reports/observability/ast-index.rollout.json",
                        "thresholds": {
                            "quality_min": 0.8,
                            "latency_p95_ms_max": 2000,
                            "fallback_rate_max": 0.25,
                        },
                    }
                }
            }

            with mock.patch.object(doctor.runtime, "require_plugin_root", return_value=plugin_root):
                with mock.patch.object(
                    doctor.runtime,
                    "capture_plugin_write_safety_snapshot",
                    return_value={"enabled": False, "supported": True, "entries": []},
                ):
                    with mock.patch.object(doctor, "resolve_project_root", return_value=(workspace_root, project_root)):
                        with mock.patch.object(doctor, "_check_binary", return_value=(True, "/usr/bin/mock")):
                            with mock.patch.object(doctor, "_check_loop_observability", return_value=(True, "ok")):
                                with mock.patch.object(doctor.runtime, "load_gates_config", return_value=gates_payload):
                                    with mock.patch.object(
                                        doctor.ast_index,
                                        "probe_readiness",
                                        return_value={
                                            "mode": "auto",
                                            "required": False,
                                            "available": True,
                                            "index_ready": True,
                                            "reason_code": "",
                                            "binary": "ast-index",
                                            "version": "ast-index 0.0.1",
                                        },
                                    ):
                                        out = io.StringIO()
                                        err = io.StringIO()
                                        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                                            rc = doctor.main([])
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("ast-index wave-2 rollout", text)
            self.assertIn("status=missing_metrics", text)

    def test_ast_rollout_wave2_enforced_threshold_miss_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doctor-rollout-enforced-") as tmpdir:
            workspace_root = Path(tmpdir)
            project_root = _seed_project(workspace_root)
            plugin_root = workspace_root / "plugin"
            for name in ("commands", "agents", "hooks", "tools", "templates"):
                (plugin_root / name).mkdir(parents=True, exist_ok=True)

            metrics_path = project_root / "reports" / "observability" / "ast-index.rollout.json"
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(
                '{"quality_score": 0.50, "latency_p95_ms": 3500, "fallback_rate": 0.70}\n',
                encoding="utf-8",
            )
            gates_payload = {
                "ast_index": {
                    "rollout_wave2": {
                        "enabled": True,
                        "decision_mode": "hard",
                        "scopes": ["implement", "review", "qa"],
                        "metrics_artifact": "aidd/reports/observability/ast-index.rollout.json",
                        "thresholds": {
                            "quality_min": 0.8,
                            "latency_p95_ms_max": 2000,
                            "fallback_rate_max": 0.25,
                        },
                    }
                }
            }

            with mock.patch.object(doctor.runtime, "require_plugin_root", return_value=plugin_root):
                with mock.patch.object(
                    doctor.runtime,
                    "capture_plugin_write_safety_snapshot",
                    return_value={"enabled": False, "supported": True, "entries": []},
                ):
                    with mock.patch.object(doctor, "resolve_project_root", return_value=(workspace_root, project_root)):
                        with mock.patch.object(doctor, "_check_binary", return_value=(True, "/usr/bin/mock")):
                            with mock.patch.object(doctor, "_check_loop_observability", return_value=(True, "ok")):
                                with mock.patch.object(doctor.runtime, "load_gates_config", return_value=gates_payload):
                                    with mock.patch.object(
                                        doctor.ast_index,
                                        "probe_readiness",
                                        return_value={
                                            "mode": "auto",
                                            "required": False,
                                            "available": True,
                                            "index_ready": True,
                                            "reason_code": "",
                                            "binary": "ast-index",
                                            "version": "ast-index 0.0.1",
                                        },
                                    ):
                                        out = io.StringIO()
                                        err = io.StringIO()
                                        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                                            rc = doctor.main([])
            self.assertEqual(rc, 1)
            text = out.getvalue()
            self.assertIn("ast-index wave-2 rollout", text)
            self.assertIn("status=blocked", text)
            self.assertIn("thresholds are not satisfied", text)

    def test_memory_rollout_advisory_missing_metrics_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doctor-memory-rollout-advisory-") as tmpdir:
            workspace_root = Path(tmpdir)
            project_root = _seed_project(workspace_root)
            plugin_root = workspace_root / "plugin"
            for name in ("commands", "agents", "hooks", "tools", "templates"):
                (plugin_root / name).mkdir(parents=True, exist_ok=True)

            gates_payload = {
                "memory": {
                    "rollout_hardening": {
                        "enabled": True,
                        "decision_mode": "advisory",
                        "metrics_artifact": "aidd/reports/observability/memory.rollout.json",
                        "thresholds": {
                            "memory_slice_coverage_min": 0.9,
                            "rg_without_slice_rate_max": 0.1,
                            "decisions_pack_stale_events_max": 0,
                        },
                    }
                }
            }

            with mock.patch.object(doctor.runtime, "require_plugin_root", return_value=plugin_root):
                with mock.patch.object(
                    doctor.runtime,
                    "capture_plugin_write_safety_snapshot",
                    return_value={"enabled": False, "supported": True, "entries": []},
                ):
                    with mock.patch.object(doctor, "resolve_project_root", return_value=(workspace_root, project_root)):
                        with mock.patch.object(doctor, "_check_binary", return_value=(True, "/usr/bin/mock")):
                            with mock.patch.object(doctor, "_check_loop_observability", return_value=(True, "ok")):
                                with mock.patch.object(doctor.runtime, "load_gates_config", return_value=gates_payload):
                                    with mock.patch.object(
                                        doctor.ast_index,
                                        "probe_readiness",
                                        return_value={
                                            "mode": "auto",
                                            "required": False,
                                            "available": True,
                                            "index_ready": True,
                                            "reason_code": "",
                                            "binary": "ast-index",
                                            "version": "ast-index 0.0.1",
                                        },
                                    ):
                                        out = io.StringIO()
                                        err = io.StringIO()
                                        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                                            rc = doctor.main([])
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("memory hardening rollout", text)
            self.assertIn("status=missing_metrics", text)

    def test_memory_rollout_hard_threshold_miss_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doctor-memory-rollout-hard-") as tmpdir:
            workspace_root = Path(tmpdir)
            project_root = _seed_project(workspace_root)
            plugin_root = workspace_root / "plugin"
            for name in ("commands", "agents", "hooks", "tools", "templates"):
                (plugin_root / name).mkdir(parents=True, exist_ok=True)

            metrics_path = project_root / "reports" / "observability" / "memory.rollout.json"
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(
                '{"memory_slice_coverage": 0.50, "rg_without_slice_rate": 0.50, "decisions_pack_stale_events": 2}\n',
                encoding="utf-8",
            )
            gates_payload = {
                "memory": {
                    "rollout_hardening": {
                        "enabled": True,
                        "decision_mode": "hard",
                        "metrics_artifact": "aidd/reports/observability/memory.rollout.json",
                        "thresholds": {
                            "memory_slice_coverage_min": 0.9,
                            "rg_without_slice_rate_max": 0.1,
                            "decisions_pack_stale_events_max": 0,
                        },
                    }
                }
            }

            with mock.patch.object(doctor.runtime, "require_plugin_root", return_value=plugin_root):
                with mock.patch.object(
                    doctor.runtime,
                    "capture_plugin_write_safety_snapshot",
                    return_value={"enabled": False, "supported": True, "entries": []},
                ):
                    with mock.patch.object(doctor, "resolve_project_root", return_value=(workspace_root, project_root)):
                        with mock.patch.object(doctor, "_check_binary", return_value=(True, "/usr/bin/mock")):
                            with mock.patch.object(doctor, "_check_loop_observability", return_value=(True, "ok")):
                                with mock.patch.object(doctor.runtime, "load_gates_config", return_value=gates_payload):
                                    with mock.patch.object(
                                        doctor.ast_index,
                                        "probe_readiness",
                                        return_value={
                                            "mode": "auto",
                                            "required": False,
                                            "available": True,
                                            "index_ready": True,
                                            "reason_code": "",
                                            "binary": "ast-index",
                                            "version": "ast-index 0.0.1",
                                        },
                                    ):
                                        out = io.StringIO()
                                        err = io.StringIO()
                                        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                                            rc = doctor.main([])
            self.assertEqual(rc, 1)
            text = out.getvalue()
            self.assertIn("memory hardening rollout", text)
            self.assertIn("status=blocked", text)
            self.assertIn("thresholds are not satisfied", text)


if __name__ == "__main__":
    unittest.main()
