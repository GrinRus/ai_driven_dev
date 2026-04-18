from __future__ import annotations

import runpy

import argparse
import json
import shutil
from pathlib import Path
from typing import List

_PLUGIN_ROOT = runpy.run_path(
    next(
        parent / "aidd_runtime" / "plugin_bootstrap.py"
        for parent in Path(__file__).resolve().parents
        if (parent / "aidd_runtime" / "plugin_bootstrap.py").is_file()
    )
)["ensure_plugin_root_on_path"](__file__)

from aidd_runtime import runtime
from aidd_runtime.resources import DEFAULT_PROJECT_SUBDIR

SKILL_TEMPLATE_SEEDS: tuple[tuple[str, str], ...] = (
    ("skills/aidd-core/templates/workspace-agents.md", "AGENTS.md"),
    ("skills/aidd-core/templates/stage-lexicon.md", "docs/shared/stage-lexicon.md"),
    ("skills/aidd-core/templates/index.schema.json", "docs/index/schema.json"),
    ("skills/idea-new/templates/prd.template.md", "docs/prd/template.md"),
    ("skills/plan-new/templates/plan.template.md", "docs/plan/template.md"),
    ("skills/researcher/templates/research.template.md", "docs/research/template.md"),
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


_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "__pycache__",
    "aidd",
}


def _detect_qa_test_command_entries(workspace_root: Path) -> list[dict]:
    entries: list[dict] = []

    def add_entry(entry_id: str, command: list[str], cwd: str, profiles: list[str]) -> None:
        if not command:
            return
        for existing in entries:
            if existing.get("command") == command and existing.get("cwd") == cwd:
                return
        entries.append(
            {
                "id": entry_id,
                "command": command,
                "cwd": cwd or ".",
                "profiles": profiles,
            }
        )

    def rel_parent(path: Path) -> str:
        parent = path.parent
        if parent == workspace_root:
            return "."
        return parent.relative_to(workspace_root).as_posix()

    for candidate in sorted(workspace_root.rglob("gradlew")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("gradle_test", ["./gradlew", "test"], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("mvnw")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("maven_test", ["./mvnw", "test"], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("pom.xml")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("maven_test", ["mvn", "test"], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("go.mod")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("go_test", ["go", "test", "./..."], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("Cargo.toml")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("cargo_test", ["cargo", "test"], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("pyproject.toml")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("pytest", ["python3", "-m", "pytest"], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("requirements.txt")):
        if not candidate.is_file():
            continue
        if any(part in _SKIP_DIRS for part in candidate.relative_to(workspace_root).parts):
            continue
        add_entry("pytest", ["python3", "-m", "pytest"], rel_parent(candidate), ["targeted", "full"])

    for candidate in sorted(workspace_root.rglob("package.json")):
        if not candidate.is_file():
            continue
        rel = candidate.relative_to(workspace_root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        lock_parent = candidate.parent
        pnpm_lock = lock_parent / "pnpm-lock.yaml"
        yarn_lock = lock_parent / "yarn.lock"
        if pnpm_lock.exists():
            add_entry("pnpm_test", ["pnpm", "test"], rel_parent(candidate), ["targeted", "full"])
        elif yarn_lock.exists():
            add_entry("yarn_test", ["yarn", "test"], rel_parent(candidate), ["targeted", "full"])
        else:
            add_entry("npm_test", ["npm", "test", "--", "--watch=false"], rel_parent(candidate), ["targeted", "full"])

    if not entries and (workspace_root / "Makefile").exists():
        add_entry("make_test", ["make", "test"], ".", ["targeted", "full"])
    return entries


def _bootstrap_qa_tests_contract(project_root: Path, *, detect_root: Path, force: bool) -> None:
    gates_path = project_root / "config" / "gates.json"
    try:
        payload = json.loads(gates_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return

    qa_cfg = payload.get("qa")
    if isinstance(qa_cfg, bool):
        qa_cfg = {"enabled": qa_cfg}
    if not isinstance(qa_cfg, dict):
        qa_cfg = {}
        payload["qa"] = qa_cfg

    tests_cfg = qa_cfg.get("tests")
    if not isinstance(tests_cfg, dict):
        tests_cfg = {}
        qa_cfg["tests"] = tests_cfg

    existing_commands = tests_cfg.get("commands")
    if isinstance(existing_commands, list) and existing_commands and not force:
        return

    detected_entries = _detect_qa_test_command_entries(detect_root)
    tests_cfg["contract_version"] = int(tests_cfg.get("contract_version") or 1)
    tests_cfg["filters_default"] = tests_cfg.get("filters_default") or []
    tests_cfg["when_default"] = str(tests_cfg.get("when_default") or "manual")
    tests_cfg["reason_default"] = str(tests_cfg.get("reason_default") or "auto-bootstrap from workspace tooling")
    if detected_entries:
        tests_cfg["profile_default"] = str(tests_cfg.get("profile_default") or "targeted")
        tests_cfg["commands"] = detected_entries
    else:
        tests_cfg["profile_default"] = "none"
        tests_cfg["commands"] = []

    gates_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[aidd:init] qa.tests contract bootstrapped in {gates_path} "
        f"(commands={len(tests_cfg.get('commands') or [])})"
    )


def run_init(target: Path, extra_args: List[str] | None = None) -> None:
    extra_args = extra_args or []
    workspace_root, project_root = runtime.resolve_roots(target, create=True)

    force = "--force" in extra_args
    ignored = [arg for arg in extra_args if arg not in {"--force"}]
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
    loops_reports = project_root / "reports" / "loops"
    loops_reports.mkdir(parents=True, exist_ok=True)
    _bootstrap_qa_tests_contract(project_root, detect_root=workspace_root, force=force)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate workflow scaffolding in the current workspace.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    script_args: list[str] = []
    if args.force:
        script_args.append("--force")
    run_init(Path.cwd().resolve(), script_args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
