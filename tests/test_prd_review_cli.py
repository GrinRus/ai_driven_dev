import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, ensure_project_root


def _load_prd_review_module():
    module_path = REPO_ROOT / "skills" / "aidd-core" / "runtime" / "prd_review.py"
    module_name = "test_prd_review_module"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_prd(project_root: Path, ticket: str, *, status: str, note: str = "") -> Path:
    prd_path = project_root / "docs" / "prd" / f"{ticket}.prd.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# PRD {ticket}",
        "",
        "## Scope",
        "Stable scope details.",
        "",
        "## PRD Review",
        f"Status: {status}",
    ]
    if note:
        lines.extend(["", note])
    prd_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return prd_path


class PrdReviewCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_prd_review_module()

    def test_prd_review_writes_report_for_ready_prd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-READY"
            _write_prd(project_root, ticket, status="READY")
            (project_root / "reports" / "prd").mkdir(parents=True, exist_ok=True)
            report_path = project_root / "reports" / "prd" / f"{ticket}.json"

            cwd = os.getcwd()
            try:
                os.chdir(project_root)
                rc = self.mod.main(["--ticket", ticket, "--report", str(report_path)])
            finally:
                os.chdir(cwd)

            self.assertEqual(rc, 0)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("ticket"), ticket)
            self.assertEqual(payload.get("status"), "ready")
            self.assertEqual(payload.get("recommended_status"), "ready")

    def test_require_ready_fails_for_pending_prd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-PENDING"
            _write_prd(project_root, ticket, status="PENDING")
            (project_root / "reports" / "prd").mkdir(parents=True, exist_ok=True)

            cwd = os.getcwd()
            try:
                os.chdir(project_root)
                rc = self.mod.main(["--ticket", ticket, "--require-ready"])
            finally:
                os.chdir(cwd)

            self.assertEqual(rc, 2)

    def test_require_ready_passes_for_ready_prd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-REQUIRE-READY"
            _write_prd(project_root, ticket, status="READY")
            (project_root / "reports" / "prd").mkdir(parents=True, exist_ok=True)

            cwd = os.getcwd()
            try:
                os.chdir(project_root)
                rc = self.mod.main(["--ticket", ticket, "--require-ready"])
            finally:
                os.chdir(cwd)

            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
