from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import runtime
from aidd_runtime.resources import DEFAULT_PROJECT_SUBDIR

SKILL_TEMPLATE_SEEDS: tuple[tuple[str, str], ...] = (
    ("skills/aidd-core/templates/workspace-agents.md", "AGENTS.md"),
    ("skills/aidd-core/templates/stage-lexicon.md", "docs/shared/stage-lexicon.md"),
    ("skills/aidd-core/templates/index.schema.json", "docs/index/schema.json"),
    ("skills/idea-new/templates/prd.template.md", "docs/prd/template.md"),
    ("skills/plan-new/templates/plan.template.md", "docs/plan/template.md"),
    ("skills/researcher/templates/research.template.md", "docs/research/template.md"),
    ("skills/spec-interview/templates/spec.template.yaml", "docs/spec/template.spec.yaml"),
    ("skills/tasks-new/templates/tasklist.template.md", "docs/tasklist/template.md"),
    ("skills/aidd-loop/templates/loop-pack.template.md", "docs/loops/template.loop-pack.md"),
    ("skills/aidd-core/templates/context-pack.template.md", "reports/context/template.context-pack.md"),
)
_SEED_TARGETS = {target for _, target in SKILL_TEMPLATE_SEEDS}
_SEED_DIRECTORIES = {str(Path(target).parent.as_posix()) for target in _SEED_TARGETS}


def _is_placeholder_only_target(rel: Path) -> bool:
    rel_text = rel.as_posix()
    if rel_text in _SEED_TARGETS:
        return True
    for directory in _SEED_DIRECTORIES:
        prefix = f"{directory}/"
        if rel_text.startswith(prefix):
            return True
    return False


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
        if _is_placeholder_only_target(rel) and path.name != ".gitkeep":
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def _copy_seed_files(plugin_root: Path, project_root: Path, *, force: bool) -> list[Path]:
    copied: list[Path] = []
    for source_rel, target_rel in SKILL_TEMPLATE_SEEDS:
        source = plugin_root / source_rel
        if not source.exists():
            raise FileNotFoundError(f"required template source not found: {source}")
        target = project_root / target_rel
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _write_test_settings(workspace_root: Path, *, force: bool) -> None:
    from aidd_runtime.test_settings_defaults import detect_build_tools, test_settings_payload

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
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[aidd:init] updated .claude/settings.json (build tools: {tools_label})")
    else:
        print("[aidd:init] .claude/settings.json already contains automation.tests defaults")


def run_init(target: Path, extra_args: List[str] | None = None) -> None:
    extra_args = extra_args or []
    workspace_root, project_root = runtime.resolve_roots(target, create=True)

    force = "--force" in extra_args
    detect_build_tools = "--detect-build-tools" in extra_args
    ignored = [arg for arg in extra_args if arg not in {"--force", "--detect-build-tools"}]
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
    seeded = _copy_seed_files(plugin_root, project_root, force=force)
    total_copied = len(copied) + len(seeded)
    if total_copied:
        print(f"[aidd:init] copied {total_copied} files into {project_root}")
    else:
        print(f"[aidd:init] no changes (already initialized) in {project_root}")
    # Keep required reports directories present even if template copy was partial.
    for reports_dir in ("loops", "memory"):
        (project_root / "reports" / reports_dir).mkdir(parents=True, exist_ok=True)
    settings_path = workspace_root / ".claude" / "settings.json"
    if detect_build_tools or not settings_path.exists():
        _write_test_settings(workspace_root, force=force if detect_build_tools else False)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate workflow scaffolding in the current workspace.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
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
    if args.force:
        script_args.append("--force")
    if args.detect_build_tools:
        script_args.append("--detect-build-tools")
    run_init(Path.cwd().resolve(), script_args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
