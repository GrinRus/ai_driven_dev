import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env


def _write_prd_with_hints(project_root: Path, ticket: str, keyword: str) -> None:
    prd_path = project_root / "docs" / "prd" / f"{ticket}.prd.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        "\n".join(
            [
                "# PRD",
                "",
                "## AIDD:RESEARCH_HINTS",
                "- Paths: src",
                f"- Keywords: {keyword}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _set_ast_binary(project_root: Path, binary_name: str) -> None:
    config_path = project_root / "config" / "conventions.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    ast_cfg = payload.get("ast_index") if isinstance(payload.get("ast_index"), dict) else {}
    ast_cfg["binary"] = binary_name
    payload["ast_index"] = ast_cfg
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _set_ast_required(project_root: Path, *, mode: str, required: bool) -> None:
    gates_path = project_root / "config" / "gates.json"
    payload = json.loads(gates_path.read_text(encoding="utf-8"))
    ast_cfg = payload.get("ast_index") if isinstance(payload.get("ast_index"), dict) else {}
    ast_cfg["mode"] = mode
    ast_cfg["required"] = required
    payload["ast_index"] = ast_cfg
    gates_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class AstIndexResearchIntegrationTests(unittest.TestCase):
    def test_research_auto_writes_ast_pack_with_stub_binary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-ast-research-stub-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )
            ticket = "AST-STUB-1"
            _write_prd_with_hints(project_root, ticket, "CheckoutService")

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "app.py").write_text("class CheckoutService:\n    pass\n", encoding="utf-8")

            bin_dir = workspace / ".bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            stub_path = bin_dir / "ast-index"
            stub_path.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'cmd=\"${1:-}\"',
                        'if [[ \"$cmd\" == \"--version\" ]]; then',
                        "  echo 'ast-index 0.0.0-test'",
                        "  exit 0",
                        "fi",
                        'if [[ \"$cmd\" == \"stats\" ]]; then',
                        "  echo '{\"status\":\"ok\",\"indexed_files\":1}'",
                        "  exit 0",
                        "fi",
                        'if [[ \"$cmd\" == \"search\" ]]; then',
                        "  echo '{\"results\":[{\"name\":\"CheckoutService\",\"kind\":\"class\",\"path\":\"src/app.py\",\"line\":1,\"column\":1,\"snippet\":\"class CheckoutService:\"}]}'",
                        "  exit 0",
                        "fi",
                        'if [[ \"$cmd\" == \"rebuild\" ]]; then',
                        "  exit 0",
                        "fi",
                        "echo '{\"results\":[]}'",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            stub_path.chmod(0o755)

            env = cli_env()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            result = subprocess.run(
                cli_cmd("research", "--ticket", ticket, "--auto"),
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            ast_pack = project_root / "reports" / "research" / f"{ticket}-ast.pack.json"
            self.assertTrue(ast_pack.exists())
            payload = json.loads(ast_pack.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.ast.pack.v1")
            rows = payload.get("matches", {}).get("rows", [])
            self.assertGreaterEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "CheckoutService")
            warnings = payload.get("warnings") or []
            self.assertEqual(warnings, [])

    def test_research_auto_falls_back_to_rg_when_binary_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-ast-research-fallback-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )
            ticket = "AST-FALLBACK-1"
            _write_prd_with_hints(project_root, ticket, "fallback_marker")
            _set_ast_binary(project_root, "ast-index-missing-for-test")

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "service.py").write_text("def fallback_marker_handler():\n    return True\n", encoding="utf-8")

            result = subprocess.run(
                cli_cmd("research", "--ticket", ticket, "--auto"),
                cwd=workspace,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            ast_pack = project_root / "reports" / "research" / f"{ticket}-ast.pack.json"
            self.assertTrue(ast_pack.exists())
            payload = json.loads(ast_pack.read_text(encoding="utf-8"))
            warnings = payload.get("warnings") or []
            self.assertIn("ast_index_binary_missing", warnings)
            self.assertIn("ast_index_fallback_rg", warnings)
            rows = payload.get("matches", {}).get("rows", [])
            self.assertGreaterEqual(len(rows), 1)

    def test_research_blocks_when_ast_required_and_binary_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-ast-research-required-") as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )
            ticket = "AST-REQ-1"
            _write_prd_with_hints(project_root, ticket, "required_marker")
            _set_ast_binary(project_root, "ast-index-missing-for-required-test")
            _set_ast_required(project_root, mode="required", required=True)

            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "required.py").write_text("def required_marker_func():\n    return True\n", encoding="utf-8")

            result = subprocess.run(
                cli_cmd("research", "--ticket", ticket, "--auto"),
                cwd=workspace,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("reason_code=ast_index_binary_missing", result.stderr)
            self.assertIn("next_action", result.stderr)


if __name__ == "__main__":
    unittest.main()
