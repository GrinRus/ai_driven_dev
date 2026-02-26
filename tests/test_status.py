import json
import subprocess
import tempfile
from pathlib import Path

from .helpers import cli_cmd, cli_env, ensure_project_root, write_active_feature, write_active_stage, write_file


def test_status_refresh_uses_rlm_pack_and_ignores_legacy_research_files():
    with tempfile.TemporaryDirectory(prefix="aidd-status-") as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        project_root = ensure_project_root(workspace)
        ticket = "STATUS-1"

        write_active_feature(project_root, ticket)
        write_active_stage(project_root, "review")
        write_file(project_root, f"docs/research/{ticket}.md", "# Research\n\nStatus: reviewed\n")
        write_file(
            project_root,
            f"reports/research/{ticket}-rlm.pack.json",
            json.dumps(
                {
                    "schema": "aidd.report.pack.v1",
                    "pack_version": "v1",
                    "type": "rlm",
                    "kind": "pack",
                    "ticket": ticket,
                    "status": "ready",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        write_file(
            project_root,
            f"reports/memory/{ticket}.semantic.pack.json",
            json.dumps(
                {
                    "schema": "aidd.memory.semantic.v1",
                    "pack_version": "v1",
                    "type": "memory-semantic",
                    "kind": "pack",
                    "ticket": ticket,
                    "status": "ok",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        # Legacy files may exist in historical workspaces, but must be ignored by status/index surfaces.
        legacy_context_suffix = "-context.json"
        legacy_targets_suffix = "-targets.json"
        write_file(project_root, f"reports/research/{ticket}{legacy_context_suffix}", "{bad-json")
        write_file(project_root, f"reports/research/{ticket}{legacy_targets_suffix}", "{bad-json")

        result = subprocess.run(
            cli_cmd("status", "--ticket", ticket, "--refresh"),
            cwd=workspace,
            text=True,
            capture_output=True,
            env=cli_env(),
        )

        assert result.returncode == 0, result.stderr
        assert f"aidd/reports/research/{ticket}-rlm.pack.json" in result.stdout
        assert f"aidd/reports/memory/{ticket}.semantic.pack.json" in result.stdout
        assert f"{ticket}{legacy_context_suffix}" not in result.stdout
        assert f"{ticket}{legacy_targets_suffix}" not in result.stdout

        index_path = project_root / "docs" / "index" / f"{ticket}.json"
        assert index_path.exists()
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        reports = index_payload.get("reports") or []
        assert f"aidd/reports/research/{ticket}-rlm.pack.json" in reports
        assert f"aidd/reports/memory/{ticket}.semantic.pack.json" in reports
        assert all(not str(item).endswith(f"{ticket}{legacy_context_suffix}") for item in reports)
        assert all(not str(item).endswith(f"{ticket}{legacy_targets_suffix}") for item in reports)
