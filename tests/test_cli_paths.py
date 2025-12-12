import subprocess

from tests.helpers import cli_cmd


def test_cli_init_creates_aidd_under_workspace(tmp_path):
    result = subprocess.run(
        cli_cmd("init", "--target", ".", "--commit-mode", "ticket-prefix", "--force"),
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "aidd" / ".claude" / "settings.json").is_file()


def test_cli_command_errors_when_workflow_missing(tmp_path):
    result = subprocess.run(
        cli_cmd("research", "--target", ".", "--ticket", "DEMO-1", "--targets-only", "--auto"),
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "workflow not found at" in result.stderr
    assert "aidd" in result.stderr
