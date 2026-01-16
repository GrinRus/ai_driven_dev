import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from .helpers import PROJECT_SUBDIR, TEMPLATES_ROOT, cli_cmd, cli_env

# Represent key artefacts that must match templates byte-for-byte after bootstrap.
CRITICAL_FILES: Iterable[str] = (
    ".markdownlint.yaml",
    "AGENTS.md",
    "conventions.md",
    "config/context_gc.json",
    "config/conventions.json",
    "config/gates.json",
    "docs/prd/template.md",
    "docs/spec/template.spec.yaml",
    "docs/tasklist/template.md",
    "docs/research/template.md",
    "docs/anchors/idea.md",
)

PROJECT_DIRECTORIES = (
    "config",
    "docs",
    "reports",
)
WORKSPACE_DIRECTORIES = ()


def _run_bootstrap(target: Path, *extra_args: str) -> None:
    project_root = target / PROJECT_SUBDIR
    project_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        cli_cmd("init", "--target", str(target), *extra_args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=cli_env(),
    )


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_hook_commands(settings_path: Path) -> list[str]:
    data = json.loads(settings_path.read_text(encoding="utf-8"))

    def collect(entries):
        commands = []
        if isinstance(entries, list):
            for entry in entries:
                hooks = entry.get("hooks") if isinstance(entry, dict) else None
                if isinstance(hooks, list):
                    for hook in hooks:
                        cmd = hook.get("command")
                        if isinstance(cmd, str):
                            commands.append(cmd)
        return commands

    result = []
    hooks_section = data.get("hooks", {})
    if isinstance(hooks_section, dict):
        result.extend(collect(hooks_section.get("PreToolUse")))
        result.extend(collect(hooks_section.get("PostToolUse")))

    presets = data.get("presets", {}).get("list", {})
    if isinstance(presets, dict):
        for preset in presets.values():
            preset_hooks = preset.get("hooks")
            if isinstance(preset_hooks, dict):
                result.extend(collect(preset_hooks.get("PreToolUse")))
                result.extend(collect(preset_hooks.get("PostToolUse")))
    return result


def test_bootstrap_copies_payload_files_and_directories():
    with tempfile.TemporaryDirectory(prefix="claude-workflow-e2e-") as tmpdir:
        target = Path(tmpdir)
        _run_bootstrap(target)
        project_root = target / PROJECT_SUBDIR

        for directory in PROJECT_DIRECTORIES:
            assert (project_root / directory).is_dir(), f"{directory} must exist after bootstrap"
        for directory in WORKSPACE_DIRECTORIES:
            assert (target / directory).is_dir(), f"{directory} must exist after bootstrap"

        for relative in CRITICAL_FILES:
            payload_file = TEMPLATES_ROOT / relative
            project_file = project_root / relative
            assert payload_file.is_file(), f"template missing {relative}"
            assert project_file.is_file(), f"project missing {relative}"
            assert _hash_file(payload_file) == _hash_file(project_file), f"{relative} mismatch vs payload"


def test_bootstrap_force_overwrites_modified_files():
    with tempfile.TemporaryDirectory(prefix="claude-workflow-force-") as tmpdir:
        target = Path(tmpdir)
        _run_bootstrap(target)

        project_root = target / PROJECT_SUBDIR
        gate_workflow = project_root / "config" / "gates.json"
        gate_workflow.write_text("# modified\n", encoding="utf-8")
        assert "modified" in gate_workflow.read_text(encoding="utf-8")

        _run_bootstrap(target, "--force")

        payload_gate = TEMPLATES_ROOT / "config" / "gates.json"
        assert _hash_file(gate_workflow) == _hash_file(payload_gate), "force bootstrap must restore template version"
