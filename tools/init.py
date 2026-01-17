from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import List

from tools import runtime
from tools.resources import DEFAULT_PROJECT_SUBDIR


def _copy_tree(src: Path, dest: Path, *, force: bool) -> list[Path]:
    copied: list[Path] = []
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def run_init(target: Path, extra_args: List[str] | None = None) -> None:
    extra_args = extra_args or []
    workspace_root, project_root = runtime.resolve_roots(target, create=True)
    current_version = runtime.read_template_version(project_root)
    if current_version and current_version != runtime.VERSION:
        print(
            f"[aidd] existing template version {current_version} detected;"
            f" CLI {runtime.VERSION} will refresh files."
        )

    force = "--force" in extra_args
    ignored = [arg for arg in extra_args if arg != "--force"]
    if ignored:
        print(f"[aidd] init flags ignored in marketplace-only mode: {' '.join(ignored)}")

    plugin_root = runtime.require_plugin_root()
    templates_root = plugin_root / "templates" / DEFAULT_PROJECT_SUBDIR
    if not templates_root.exists():
        raise FileNotFoundError(
            f"templates not found at {templates_root}. "
            "Run '/feature-dev-aidd:aidd-init' from the plugin repository."
        )

    project_root.mkdir(parents=True, exist_ok=True)
    copied = _copy_tree(templates_root, project_root, force=force)
    if copied:
        print(f"[aidd:init] copied {len(copied)} files into {project_root}")
    else:
        print(f"[aidd:init] no changes (already initialized) in {project_root}")
    runtime.write_template_version(project_root)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate workflow scaffolding in the target directory.",
    )
    parser.add_argument(
        "--target",
        default=".",
        help="Workspace root for the workflow (default: current; workflow always lives in ./aidd).",
    )
    parser.add_argument(
        "--commit-mode",
        choices=("ticket-prefix", "conventional", "mixed"),
        default="ticket-prefix",
        help="Commit message policy enforced in config/conventions.json.",
    )
    parser.add_argument(
        "--enable-ci",
        action="store_true",
        help="Add GitHub Actions workflow (manual trigger).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without modifying files.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    script_args = ["--commit-mode", args.commit_mode]
    if args.enable_ci:
        script_args.append("--enable-ci")
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    run_init(Path(args.target).resolve(), script_args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
