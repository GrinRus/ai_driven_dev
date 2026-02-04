import json
import subprocess
from textwrap import dedent

from tests.helpers import (
    cli_cmd,
    cli_env,
    ensure_gates_config,
    ensure_project_root,
    write_active_feature,
    write_active_stage,
    write_file,
    write_tasklist_ready,
)


def _write_plan(root, ticket: str) -> None:
    write_file(
        root,
        f"docs/plan/{ticket}.md",
        dedent(
            f"""\
            Status: READY

            ## AIDD:ITERATIONS
            - iteration_id: I1
              - Goal: bootstrap
            - iteration_id: I2
              - Goal: follow-up
            """
        ),
    )


def test_tasklist_cache_invalidates_on_config_change(tmp_path):
    project_root = ensure_project_root(tmp_path)
    ticket = "CACHE-1"
    write_active_feature(project_root, ticket)
    write_active_stage(project_root, "implement")
    ensure_gates_config(project_root)
    _write_plan(project_root, ticket)
    write_tasklist_ready(project_root, ticket)

    first = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert second.returncode == 0, second.stderr
    assert "cache hit" in second.stderr.lower()

    gates_path = project_root / "config" / "gates.json"
    data = json.loads(gates_path.read_text(encoding="utf-8"))
    data["tests_required"] = "hard"
    gates_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    third = subprocess.run(
        cli_cmd("tasklist-check", "--ticket", ticket),
        cwd=project_root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )
    assert third.returncode == 0, third.stderr
    assert "cache hit" not in third.stderr.lower()
