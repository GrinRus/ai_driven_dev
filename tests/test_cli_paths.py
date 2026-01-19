import subprocess

from tests.helpers import cli_cmd, cli_env


def test_cli_init_creates_aidd_under_workspace(tmp_path):
    result = subprocess.run(
        cli_cmd("init", "--force"),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "aidd").is_dir()


def test_cli_command_errors_when_workflow_missing(tmp_path):
    result = subprocess.run(
        cli_cmd("research", "--ticket", "DEMO-1", "--targets-only", "--auto"),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=cli_env(),
    )

    assert result.returncode == 1
    assert "workflow not found at" in result.stderr
    assert "aidd" in result.stderr
