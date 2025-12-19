import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from .helpers import PAYLOAD_ROOT, PROJECT_SUBDIR

# Represent key artefacts that must match payload byte-for-byte after bootstrap.
CRITICAL_FILES: Iterable[str] = (
    "commands/idea-new.md",
    ".claude/hooks/gate-workflow.sh",
    ".claude/hooks/gate-qa.sh",
    ".claude/hooks/_vendor/claude_workflow_cli/tools/analyst_guard.py",
    "config/context_gc.json",
    "config/conventions.json",
    "claude-presets/feature-prd.yaml",
    "claude-presets/advanced/feature-design.yaml",
    "docs/customization.md",
    "docs/prd.template.md",
    "scripts/ci-lint.sh",
    "scripts/context_gc/hooklib.py",
    "scripts/context_gc/precompact_snapshot.py",
    "scripts/context_gc/pretooluse_guard.py",
    "scripts/context_gc/sessionstart_inject.py",
    "scripts/context_gc/userprompt_guard.py",
    "scripts/context_gc/working_set_builder.py",
    "CLAUDE.md",
    "conventions.md",
)

REQUIRED_DIRECTORIES = (
    ".claude/hooks",
    "claude-presets",
    "config",
    "docs",
    "scripts",
    "scripts/context_gc",
    "tools",
)


def _run_bootstrap(target: Path, *extra_args: str) -> None:
    env = os.environ.copy()
    template = PAYLOAD_ROOT
    env["CLAUDE_TEMPLATE_DIR"] = str(template)
    project_root = target / PROJECT_SUBDIR
    project_root.mkdir(parents=True, exist_ok=True)
    cmd = ["bash", str(template / "init-claude-workflow.sh"), "--commit-mode", "ticket-prefix", *extra_args]
    subprocess.run(cmd, cwd=project_root, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


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

        for directory in REQUIRED_DIRECTORIES:
            assert (project_root / directory).is_dir(), f"{directory} must exist after bootstrap"

        for relative in CRITICAL_FILES:
            payload_file = PAYLOAD_ROOT / relative
            project_file = project_root / relative
            assert payload_file.is_file(), f"payload missing {relative}"
            assert project_file.is_file(), f"project missing {relative}"
            assert _hash_file(payload_file) == _hash_file(project_file), f"{relative} mismatch vs payload"

        # settings.json must exist, enable the plugin, and avoid $CLAUDE_PROJECT_DIR placeholders.
        settings_path = project_root / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data.get("enabledPlugins", {}).get("feature-dev-aidd@aidd-local"), "plugin should be enabled"
        assert "$CLAUDE_PROJECT_DIR" not in settings_path.read_text(encoding="utf-8"), "placeholders must be rewritten"


def test_bootstrap_force_overwrites_modified_files():
    with tempfile.TemporaryDirectory(prefix="claude-workflow-force-") as tmpdir:
        target = Path(tmpdir)
        _run_bootstrap(target)

        project_root = target / PROJECT_SUBDIR
        gate_workflow = project_root / ".claude" / "hooks" / "gate-workflow.sh"
        gate_workflow.write_text("# modified\n", encoding="utf-8")
        assert "modified" in gate_workflow.read_text(encoding="utf-8")

        _run_bootstrap(target, "--force")

        payload_gate = PAYLOAD_ROOT / ".claude" / "hooks" / "gate-workflow.sh"
        assert _hash_file(gate_workflow) == _hash_file(payload_gate), "force bootstrap must restore payload version"


def test_bootstrap_prompt_locale_en():
    with tempfile.TemporaryDirectory(prefix="claude-workflow-en-") as tmpdir:
        target = Path(tmpdir)
        _run_bootstrap(target, "--prompt-locale", "en")
        project_root = target / PROJECT_SUBDIR

        analyst = (project_root / ".claude" / "agents" / "analyst.md").read_text(encoding="utf-8")
        idea = (project_root / ".claude" / "commands" / "idea-new.md").read_text(encoding="utf-8")
        assert "lang: en" in analyst
        assert "lang: en" in idea
