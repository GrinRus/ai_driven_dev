from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Type


_DEBUG_FLAGS = {"1", "true", "yes", "on", "debug"}
_HELP_SECTION_MARKERS = {
    "examples": re.compile(r"(?im)^\s*(examples?|пример(?:ы)?)\s*:"),
    "outputs": re.compile(r"(?im)^\s*(outputs?|artifacts?|результат(?:ы)?)\s*:"),
    "exit_codes": re.compile(r"(?im)^\s*(exit\s*codes?|return\s*codes?|коды?\s+выхода)\s*:"),
}
_OUTPUT_HINT_TOKENS = ("output", "out", "report", "result", "log", "json", "md", "pack", "path", "file")
_HELP_PATCHED = False

_PACKAGE_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_ROOT.parent
_RUNTIME_DIRS = (
    _REPO_ROOT / "skills" / "aidd-core" / "runtime",
    _REPO_ROOT / "skills" / "aidd-docio" / "runtime",
    _REPO_ROOT / "skills" / "aidd-flow-state" / "runtime",
    _REPO_ROOT / "skills" / "aidd-observability" / "runtime",
    _REPO_ROOT / "skills" / "aidd-loop" / "runtime",
    _REPO_ROOT / "skills" / "aidd-rlm" / "runtime",
    _REPO_ROOT / "skills" / "aidd-memory" / "runtime",
    _REPO_ROOT / "skills" / "aidd-init" / "runtime",
    _REPO_ROOT / "skills" / "idea-new" / "runtime",
    _REPO_ROOT / "skills" / "plan-new" / "runtime",
    _REPO_ROOT / "skills" / "researcher" / "runtime",
    _REPO_ROOT / "skills" / "review-spec" / "runtime",
    _REPO_ROOT / "skills" / "spec-interview" / "runtime",
    _REPO_ROOT / "skills" / "tasks-new" / "runtime",
    _REPO_ROOT / "skills" / "implement" / "runtime",
    _REPO_ROOT / "skills" / "review" / "runtime",
    _REPO_ROOT / "skills" / "qa" / "runtime",
    _REPO_ROOT / "skills" / "status" / "runtime",
)

# Runtime bridge for Wave 96: resolve `aidd_runtime.<module>` from
# canonical `skills/*/runtime` locations during path migration.
for runtime_dir in _RUNTIME_DIRS:
    if not runtime_dir.is_dir():
        continue
    runtime_dir_str = str(runtime_dir)
    if runtime_dir_str not in __path__:
        __path__.append(runtime_dir_str)


def _resolve_script_label() -> str:
    argv0 = (sys.argv[0] or "").strip()
    if not argv0:
        return "<command>"
    script_path = Path(argv0).expanduser()
    try:
        script_path = script_path.resolve()
    except OSError:
        pass

    plugin_root = (os.getenv("CLAUDE_PLUGIN_ROOT") or "").strip()
    if plugin_root:
        root = Path(plugin_root).expanduser()
        try:
            root = root.resolve()
            return script_path.relative_to(root).as_posix()
        except (ValueError, OSError):
            pass
    if script_path.is_absolute():
        return script_path.name
    return argv0


def _example_invocations(parser: argparse.ArgumentParser) -> list[str]:
    script = _resolve_script_label()
    base = f"python3 ${{CLAUDE_PLUGIN_ROOT}}/{script}".replace("//", "/")
    required_tokens: list[str] = []
    for action in parser._actions:  # noqa: SLF001 - argparse exposes actions through this runtime field
        if action.dest in {"help", "h"}:
            continue
        if action.option_strings and getattr(action, "required", False):
            preferred = next((item for item in action.option_strings if item.startswith("--")), action.option_strings[0])
            required_tokens.append(preferred)
            continue
        if not action.option_strings and action.dest not in {"help", argparse.SUPPRESS}:
            required_tokens.append(f"<{action.dest}>")

    examples = [f"{base} --help"]
    if required_tokens:
        examples.append(f"{base} {' '.join(required_tokens)}")
    else:
        examples.append(base)
    return examples


def _output_hints(parser: argparse.ArgumentParser) -> str:
    output_flags: list[str] = []
    for action in parser._actions:  # noqa: SLF001 - see note in _example_invocations
        for option in action.option_strings:
            lowered = option.lower()
            if any(token in lowered for token in _OUTPUT_HINT_TOKENS):
                output_flags.append(option)
    deduped = list(dict.fromkeys(output_flags))
    if not deduped:
        return "stdout: machine- and human-readable command status."
    limit = ", ".join(deduped[:6])
    suffix = ", ..." if len(deduped) > 6 else ""
    return f"stdout + files configured by: {limit}{suffix}."


def _build_help_appendix(parser: argparse.ArgumentParser) -> str:
    examples = _example_invocations(parser)
    outputs = _output_hints(parser)
    lines = [
        "",
        "Examples:",
        *(f"  {item}" for item in examples),
        "",
        "Outputs:",
        f"  {outputs}",
        "",
        "Exit codes:",
        "  0 - success.",
        "  1 - runtime/validation failure.",
        "  2 - CLI usage error (argparse).",
    ]
    return "\n".join(lines)


def _append_contract_sections(help_text: str, parser: argparse.ArgumentParser) -> str:
    missing = [name for name, pattern in _HELP_SECTION_MARKERS.items() if not pattern.search(help_text)]
    if not missing:
        return help_text
    return help_text.rstrip() + _build_help_appendix(parser) + "\n"


def _install_help_contract_patch() -> None:
    global _HELP_PATCHED
    if _HELP_PATCHED:
        return

    original_format_help = argparse.ArgumentParser.format_help

    def _patched_format_help(self: argparse.ArgumentParser) -> str:  # type: ignore[override]
        base_help = original_format_help(self)
        return _append_contract_sections(base_help, self)

    argparse.ArgumentParser.format_help = _patched_format_help  # type: ignore[assignment]
    _HELP_PATCHED = True


_install_help_contract_patch()


def _debug_enabled() -> bool:
    return os.getenv("AIDD_DEBUG", "").strip().lower() in _DEBUG_FLAGS


def _format_exception_message(exc: BaseException) -> str:
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    return " ".join(chunk.strip() for chunk in text.splitlines() if chunk.strip())


def _aidd_excepthook(exc_type: Type[BaseException], exc: BaseException, tb) -> None:
    if _debug_enabled():
        sys.__excepthook__(exc_type, exc, tb)
        return
    message = _format_exception_message(exc)
    sys.stderr.write(f"[aidd] ERROR: {message}\n")


sys.excepthook = _aidd_excepthook
