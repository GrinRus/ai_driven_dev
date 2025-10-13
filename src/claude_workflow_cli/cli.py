from __future__ import annotations

import argparse
import os
import subprocess
import sys
from contextlib import contextmanager
from importlib import metadata, resources
from pathlib import Path
from typing import Iterable, List


PAYLOAD_PACKAGE = "claude_workflow_cli.data"

try:
    VERSION = metadata.version("claude-workflow-cli")
except metadata.PackageNotFoundError:  # pragma: no cover - editable installs
    VERSION = "0.1.0"


@contextmanager
def _payload_root() -> Iterable[Path]:
    """
    Yields a concrete filesystem path that contains the bundled bootstrap
    payload (shell scripts, templates, presets, etc.).  The context manager
    ensures compatibility with zipped installations where resources can only be
    accessed via a temporary directory.
    """
    payload = resources.files(PAYLOAD_PACKAGE) / "payload"
    with resources.as_file(payload) as resolved:
        yield Path(resolved)


def _run_subprocess(
    cmd: List[str], *, cwd: Path, env: dict[str, str] | None = None
) -> int:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=run_env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"failed to execute {cmd[0]}: {exc}") from exc
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            returncode=completed.returncode, cmd=cmd, cwd=str(cwd)
        )
    return completed.returncode


def _run_init(
    target: Path,
    extra_args: List[str] | None = None,
) -> None:
    extra_args = extra_args or []
    target.mkdir(parents=True, exist_ok=True)

    with _payload_root() as payload_path:
        script = payload_path / "init-claude-workflow.sh"
        if not script.exists():
            raise FileNotFoundError(f"bootstrap script not found at {script}")
        env = {"CLAUDE_TEMPLATE_DIR": str(payload_path)}
        cmd = ["bash", str(script), *extra_args]
        _run_subprocess(cmd, cwd=target, env=env)


def _run_smoke(verbose: bool) -> None:
    with _payload_root() as payload_path:
        script = payload_path / "scripts" / "smoke-workflow.sh"
        if not script.exists():
            raise FileNotFoundError(f"smoke script not found at {script}")
        cmd = ["bash", str(script)]
        env = {}
        if verbose:
            env["SMOKE_VERBOSE"] = "1"
        # smoke script handles its own temp directory; run from payload root
        _run_subprocess(cmd, cwd=payload_path, env=env)


def _init_command(args: argparse.Namespace) -> None:
    script_args = ["--commit-mode", args.commit_mode]
    if args.enable_ci:
        script_args.append("--enable-ci")
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    _run_init(Path(args.target).resolve(), script_args)


def _preset_command(args: argparse.Namespace) -> None:
    script_args: List[str] = ["--preset", args.name]
    if args.feature:
        script_args.extend(["--feature", args.feature])
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    _run_init(Path(args.target).resolve(), script_args)


def _smoke_command(args: argparse.Namespace) -> None:
    _run_smoke(args.verbose)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-workflow",
        description="Bootstrap and manage the Claude Code workflow presets.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Generate workflow scaffolding in the target directory."
    )
    init_parser.add_argument(
        "--target",
        default=".",
        help="Directory where the workflow should be initialised (default: current)",
    )
    init_parser.add_argument(
        "--commit-mode",
        choices=("ticket-prefix", "conventional", "mixed"),
        default="ticket-prefix",
        help="Commit message policy enforced in config/conventions.json.",
    )
    init_parser.add_argument(
        "--enable-ci",
        action="store_true",
        help="Add GitHub Actions workflow (manual trigger).",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without modifying files.",
    )
    init_parser.set_defaults(func=_init_command)

    preset_parser = subparsers.add_parser(
        "preset", help="Apply a feature preset to an existing workflow."
    )
    preset_parser.add_argument(
        "name",
        choices=(
            "feature-prd",
            "feature-plan",
            "feature-impl",
            "feature-design",
            "feature-release",
        ),
        help="Name of the preset to apply.",
    )
    preset_parser.add_argument(
        "--feature",
        help="Feature slug to use when generating artefacts.",
    )
    preset_parser.add_argument(
        "--target",
        default=".",
        help="Directory containing the workflow project (default: current).",
    )
    preset_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing preset artefacts.",
    )
    preset_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without modifying files.",
    )
    preset_parser.set_defaults(func=_preset_command)

    smoke_parser = subparsers.add_parser(
        "smoke", help="Run the bundled smoke test to validate the workflow bootstrap."
    )
    smoke_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit verbose logs when running the smoke scenario.",
    )
    smoke_parser.set_defaults(func=_smoke_command)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except subprocess.CalledProcessError as exc:
        # Propagate the same exit code but provide human-friendly output.
        parser.exit(exc.returncode, f"[claude-workflow] command failed: {exc}\n")
    except Exception as exc:  # pragma: no cover - safety net
        parser.exit(1, f"[claude-workflow] {exc}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
