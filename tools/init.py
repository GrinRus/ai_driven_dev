from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import List

from tools import runtime
from tools.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root


CI_WORKFLOW_REL_PATH = ".github/workflows/aidd-manual.yml"
CI_WORKFLOW_TEMPLATE = """name: AIDD Manual Checks

on:
  workflow_dispatch:

jobs:
  aidd-manual:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: AIDD scaffold enabled
        run: |
          echo "AIDD CI scaffold is enabled."
          echo "Add project-specific lint/test/build steps to this workflow."
"""


def _copy_tree(src: Path, dest: Path, *, force: bool, dry_run: bool) -> list[Path]:
    copied: list[Path] = []
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists() and not force:
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        copied.append(target)
    return copied


def _write_test_settings(workspace_root: Path, *, force: bool, dry_run: bool) -> None:
    from tools.test_settings_defaults import detect_build_tools, test_settings_payload

    settings_path = workspace_root / ".claude" / "settings.json"
    data: dict = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[aidd:init] skip .claude/settings.json (invalid JSON): {exc}")
            return
        if not isinstance(data, dict):
            data = {}

    detected = detect_build_tools(workspace_root)
    payload = test_settings_payload(detected)
    automation = data.setdefault("automation", {})
    if not isinstance(automation, dict):
        automation = {}
        data["automation"] = automation
    tests_cfg = automation.setdefault("tests", {})
    if not isinstance(tests_cfg, dict):
        tests_cfg = {}
        automation["tests"] = tests_cfg

    updated = False
    for key, value in payload.items():
        if force or key not in tests_cfg:
            tests_cfg[key] = value
            updated = True

    if updated:
        tools_label = ", ".join(sorted(detected)) or "default"
        if dry_run:
            print(f"[aidd:init] dry-run: would update .claude/settings.json (build tools: {tools_label})")
        else:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"[aidd:init] updated .claude/settings.json (build tools: {tools_label})")
    else:
        print("[aidd:init] .claude/settings.json already contains automation.tests defaults")


def _ensure_project_file(
    project_root: Path,
    templates_root: Path,
    rel_path: str,
    fallback: str,
    *,
    dry_run: bool,
) -> bool:
    target = project_root / rel_path
    if target.exists():
        return False
    source = templates_root / rel_path
    if dry_run:
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, target)
    else:
        target.write_text(fallback, encoding="utf-8")
    return True


def _ensure_ci_workflow(workspace_root: Path, *, force: bool, dry_run: bool) -> bool:
    target = workspace_root / CI_WORKFLOW_REL_PATH
    if target.exists() and not force:
        return False
    if dry_run:
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(CI_WORKFLOW_TEMPLATE, encoding="utf-8")
    return True


def run_init(target: Path, extra_args: List[str] | None = None) -> None:
    extra_args = extra_args or []
    dry_run = "--dry-run" in extra_args
    if dry_run:
        try:
            workspace_root, project_root = runtime.resolve_roots(target, create=False)
        except FileNotFoundError:
            workspace_root, project_root = resolve_project_root(target, DEFAULT_PROJECT_SUBDIR)
    else:
        workspace_root, project_root = runtime.resolve_roots(target, create=True)

    force = "--force" in extra_args
    enable_ci = "--enable-ci" in extra_args
    detect_build_tools = "--detect-build-tools" in extra_args
    ignored = [arg for arg in extra_args if arg not in {"--enable-ci", "--force", "--dry-run", "--detect-build-tools"}]
    if ignored:
        print(f"[aidd] init flags ignored in marketplace-only mode: {' '.join(ignored)}")

    plugin_root = runtime.require_plugin_root()
    templates_root = plugin_root / "templates" / DEFAULT_PROJECT_SUBDIR
    if not templates_root.exists():
        raise FileNotFoundError(
            f"templates not found at {templates_root}. "
            "Run '/feature-dev-aidd:aidd-init' from the plugin repository."
        )

    if not dry_run:
        project_root.mkdir(parents=True, exist_ok=True)
    copied = _copy_tree(templates_root, project_root, force=force, dry_run=dry_run)
    if copied:
        action = "would copy" if dry_run else "copied"
        print(f"[aidd:init] {action} {len(copied)} files into {project_root}")
    else:
        print(f"[aidd:init] no changes (already initialized) in {project_root}")
    ensured = []
    if _ensure_project_file(project_root, templates_root, "AGENTS.md", "# AGENTS\n", dry_run=dry_run):
        ensured.append("AGENTS.md")
    if ensured:
        prefix = "would ensure" if dry_run else "ensured"
        print(f"[aidd:init] {prefix} critical artifacts: {', '.join(ensured)}")

    if enable_ci:
        created_ci = _ensure_ci_workflow(workspace_root, force=force, dry_run=dry_run)
        if created_ci:
            prefix = "would create" if dry_run else "created"
            print(f"[aidd:init] {prefix} {CI_WORKFLOW_REL_PATH}")
        else:
            print(f"[aidd:init] CI workflow already exists: {CI_WORKFLOW_REL_PATH}")

    if not dry_run:
        loops_reports = project_root / "reports" / "loops"
        loops_reports.mkdir(parents=True, exist_ok=True)
    settings_path = workspace_root / ".claude" / "settings.json"
    if detect_build_tools or not settings_path.exists():
        _write_test_settings(workspace_root, force=force if detect_build_tools else False, dry_run=dry_run)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate workflow scaffolding in the current workspace.",
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
    parser.add_argument(
        "--detect-build-tools",
        action="store_true",
        help="Populate .claude/settings.json with default automation.tests settings.",
    )
    parser.add_argument(
        "--detect-stack",
        dest="detect_build_tools",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    script_args: list[str] = []
    if args.enable_ci:
        script_args.append("--enable-ci")
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    if args.detect_build_tools:
        script_args.append("--detect-build-tools")
    run_init(Path.cwd().resolve(), script_args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
