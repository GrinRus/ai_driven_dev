from __future__ import annotations

import argparse
import json
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


def _write_test_settings(workspace_root: Path, *, force: bool) -> None:
    from tools.test_settings_defaults import detect_build_tools, test_settings_payload

    settings_path = workspace_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
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
        settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tools_label = ", ".join(sorted(detected)) or "default"
        print(f"[aidd:init] updated .claude/settings.json (build tools: {tools_label})")
    else:
        print("[aidd:init] .claude/settings.json already contains automation.tests defaults")


def run_init(target: Path, extra_args: List[str] | None = None) -> None:
    extra_args = extra_args or []
    workspace_root, project_root = runtime.resolve_roots(target, create=True)
    force = "--force" in extra_args
    detect_build_tools = "--detect-build-tools" in extra_args
    detect_stack = "--detect-stack" in extra_args
    ignored = [arg for arg in extra_args if arg not in {"--force", "--detect-build-tools", "--detect-stack"}]
    if ignored:
        print(f"[aidd] init flags ignored in marketplace-only mode: {' '.join(ignored)}")

    plugin_root = runtime.require_plugin_root()
    templates_root = plugin_root / "templates" / DEFAULT_PROJECT_SUBDIR
    root_templates = plugin_root / "templates" / "root"
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
    if root_templates.exists():
        copied_root = _copy_tree(root_templates, workspace_root, force=force)
        if copied_root:
            print(f"[aidd:init] copied {len(copied_root)} root files into {workspace_root}")
        else:
            print(f"[aidd:init] no changes in root templates for {workspace_root}")

    loops_readme = project_root / "docs" / "loops" / "README.md"
    if not loops_readme.exists():
        template_readme = templates_root / "docs" / "loops" / "README.md"
        loops_readme.parent.mkdir(parents=True, exist_ok=True)
        if template_readme.exists():
            shutil.copy2(template_readme, loops_readme)
        else:
            loops_readme.write_text("# Loop Mode\n", encoding="utf-8")
        print(f"[aidd:init] ensured loop docs at {loops_readme}")

    loops_reports = project_root / "reports" / "loops"
    loops_reports.mkdir(parents=True, exist_ok=True)
    if detect_build_tools:
        _write_test_settings(workspace_root, force=force)
    if detect_stack:
        from tools import detect_stack as detect_stack_module

        result = detect_stack_module.detect_stack(workspace_root)
        profile_path = project_root / "docs" / "architecture" / "profile.md"
        updated = detect_stack_module.update_profile(profile_path, result, force=force)
        if updated:
            print(f"[aidd:init] updated architecture profile stack hints ({profile_path})")
        else:
            print("[aidd:init] architecture profile already contains detected stack hints")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate workflow scaffolding in the current workspace.",
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
    parser.add_argument(
        "--detect-build-tools",
        action="store_true",
        help="Populate .claude/settings.json with default automation.tests settings.",
    )
    parser.add_argument(
        "--detect-stack",
        action="store_true",
        help="Detect stack markers and update architecture profile hints.",
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
    if args.detect_build_tools:
        script_args.append("--detect-build-tools")
    if args.detect_stack:
        script_args.append("--detect-stack")
    run_init(Path.cwd().resolve(), script_args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
