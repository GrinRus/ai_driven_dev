from __future__ import annotations

import argparse
import filecmp
import os
import shutil
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
        subprocess.run(cmd, cwd=str(cwd), env=run_env, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"failed to execute {cmd[0]}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"command {' '.join(cmd)} exited with code {exc.returncode};"
            " see logs above for details"
        ) from exc
    return 0


def _run_init(
    target: Path,
    extra_args: List[str] | None = None,
) -> None:
    extra_args = extra_args or []
    target.mkdir(parents=True, exist_ok=True)

    current_version = _read_template_version(target)
    if current_version and current_version != VERSION:
        print(
            f"[claude-workflow] existing template version {current_version} detected;"
            f" CLI {VERSION} will refresh files."
        )

    with _payload_root() as payload_path:
        script = payload_path / "init-claude-workflow.sh"
        if not script.exists():
            raise FileNotFoundError(f"bootstrap script not found at {script}")
        env = {"CLAUDE_TEMPLATE_DIR": str(payload_path)}
        cmd = ["bash", str(script), *extra_args]
        _run_subprocess(cmd, cwd=target, env=env)
    _write_template_version(target)


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


def _read_template_version(target: Path) -> str | None:
    version_file = target / ".claude" / ".template_version"
    if not version_file.exists():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None


def _write_template_version(target: Path) -> None:
    version_file = target / ".claude" / ".template_version"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"{VERSION}\n", encoding="utf-8")


def _iter_payload_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def _ensure_unique_backup(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.bak")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak{counter}")
        counter += 1
    return candidate


def _is_relative_to(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False


def _select_payload_entries(
    payload_path: Path, includes: Iterable[Path] | None = None
) -> list[tuple[Path, Path]]:
    include_list = list(includes or [])
    entries: list[tuple[Path, Path]] = []
    for src in _iter_payload_files(payload_path):
        rel = src.relative_to(payload_path)
        if include_list and not any(_is_relative_to(rel, inc) for inc in include_list):
            continue
        entries.append((src, rel))
    return entries


def _copy_payload_entries(
    target: Path,
    entries: Iterable[tuple[Path, Path]],
    *,
    force: bool,
    dry_run: bool,
    create_backups: bool,
) -> tuple[list[str], list[str], list[str]]:
    updated: list[str] = []
    skipped: list[str] = []
    backups: list[str] = []

    for src, rel in entries:
        dest = target / rel

        if not dest.exists():
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            updated.append(str(rel))
            continue

        try:
            identical = filecmp.cmp(src, dest, shallow=False)
        except OSError:
            identical = False

        if identical:
            if not dry_run:
                shutil.copy2(src, dest)
            updated.append(str(rel))
            continue

        if force:
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                backup_path: Path | None = None
                if create_backups:
                    backup_path = _ensure_unique_backup(dest)
                    shutil.copy2(dest, backup_path)
                    backups.append(str(backup_path.relative_to(target)))
                shutil.copy2(src, dest)
            updated.append(str(rel))
        else:
            skipped.append(str(rel))

    return updated, skipped, backups


def _normalise_include(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"include path must be relative: {value}")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"include path cannot contain '..': {value}")
    return path


def _upgrade_command(args: argparse.Namespace) -> None:
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

    current_version = _read_template_version(target)
    if current_version and current_version == VERSION:
        print(
            f"[claude-workflow] project already on template version {VERSION};"
            " upgrade will refresh files if templates changed."
        )

    with _payload_root() as payload_path:
        entries = _select_payload_entries(payload_path)
        updated, skipped, backups = _copy_payload_entries(
            target,
            entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )

    if args.dry_run:
        print(
            f"[claude-workflow] upgrade dry-run: {len(updated)} files would update,"
            f" {len(skipped)} would be skipped."
        )
        if skipped:
            print("[claude-workflow] skipped (differs locally):")
            for item in skipped:
                print(f"  - {item}")
        return

    _write_template_version(target)

    report_lines = [
        f"claude-workflow upgrade ({VERSION})",
        f"updated: {len(updated)}",
        f"skipped (manual merge required): {len(skipped)}",
        f"backups created: {len(backups)}",
        "",
    ]

    if skipped:
        report_lines.append("Skipped files:")
        report_lines.extend(f"  - {item}" for item in skipped)
        report_lines.append("")

    if backups:
        report_lines.append("Backups:")
        report_lines.extend(f"  - {item}" for item in backups)
        report_lines.append("")

    report_path = target / ".claude" / "upgrade-report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(
        f"[claude-workflow] upgrade complete: {len(updated)} files updated,"
        f" {len(skipped)} skipped. Report saved to {report_path}."
    )
    if skipped:
        print("[claude-workflow] Some files differ locally; review report for details.")


def _sync_command(args: argparse.Namespace) -> None:
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

    raw_includes = args.include or [".claude"]
    try:
        includes = [_normalise_include(item) for item in raw_includes]
    except ValueError as exc:
        raise ValueError(f"invalid include path: {exc}") from exc

    with _payload_root() as payload_path:
        for include in includes:
            if not (payload_path / include).exists():
                raise FileNotFoundError(f"payload path not found: {include}")
        entries = _select_payload_entries(payload_path, includes)
        updated, skipped, backups = _copy_payload_entries(
            target,
            entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )

    if args.dry_run:
        print(
            f"[claude-workflow] sync dry-run: {len(updated)} files would update,"
            f" {len(skipped)} would be skipped."
        )
        if skipped:
            print("[claude-workflow] skipped (differs locally):")
            for item in skipped:
                print(f"  - {item}")
        return

    if any(_is_relative_to(include, Path(".claude")) for include in includes):
        _write_template_version(target)

    print(
        f"[claude-workflow] sync complete: {len(updated)} files updated,"
        f" {len(skipped)} skipped."
    )
    if skipped:
        print("[claude-workflow] Skipped files (manual merge required):")
        for item in skipped:
            print(f"  - {item}")
    if backups:
        print("[claude-workflow] Backups:")
        for item in backups:
            print(f"  - {item}")


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

    upgrade_parser = subparsers.add_parser(
        "upgrade", help="Refresh workflow files from the latest template."
    )
    upgrade_parser.add_argument(
        "--target",
        default=".",
        help="Directory containing the workflow project (default: current).",
    )
    upgrade_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files even if they differ; backups are created first.",
    )
    upgrade_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing files.",
    )
    upgrade_parser.set_defaults(func=_upgrade_command)

    sync_parser = subparsers.add_parser(
        "sync",
        help="Synchronise payload fragments (defaults to .claude) into the target directory.",
    )
    sync_parser.add_argument(
        "--target",
        default=".",
        help="Directory containing the workflow project (default: current).",
    )
    sync_parser.add_argument(
        "--include",
        action="append",
        help=(
            "Relative payload path to sync. Can be specified multiple times; "
            "defaults to .claude if omitted."
        ),
    )
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files even if they differ; backups are created first.",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing files.",
    )
    sync_parser.set_defaults(func=_sync_command)

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
