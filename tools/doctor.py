from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from tools.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root
from tools.runtime import require_plugin_root


def _format_status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def _check_binary(name: str) -> tuple[bool, str]:
    path = shutil.which(name)
    return (path is not None), (path or "not found in PATH")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIDD install diagnostics.")
    parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (defaults to current directory).",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []
    rows: list[tuple[str, bool, str]] = []

    try:
        plugin_root = require_plugin_root()
        rows.append(("CLAUDE_PLUGIN_ROOT", True, str(plugin_root)))
    except RuntimeError as exc:
        rows.append(("CLAUDE_PLUGIN_ROOT", False, str(exc)))
        errors.append("Set CLAUDE_PLUGIN_ROOT to the plugin install path.")
        plugin_root = None

    py_ok = sys.version_info >= (3, 10)
    rows.append(("python3 (>=3.10)", py_ok, sys.executable))
    if not py_ok:
        errors.append("Upgrade Python to 3.10+ and re-run.")

    for binary in ("rg", "git"):
        ok, detail = _check_binary(binary)
        rows.append((binary, ok, detail))
        if not ok:
            errors.append(f"Install `{binary}` and ensure it is on PATH.")

    if plugin_root:
        missing = []
        for name in ("commands", "agents", "hooks", "tools", "templates"):
            if not (plugin_root / name).exists():
                missing.append(name)
        rows.append(
            (
                "plugin layout",
                not missing,
                "missing: " + ", ".join(missing) if missing else "ok",
            )
        )
        if missing:
            errors.append("Reinstall the plugin to restore missing directories.")

    target = Path(args.target).expanduser().resolve()
    workspace_root, project_root = resolve_project_root(target, DEFAULT_PROJECT_SUBDIR)
    rows.append(("workspace root", workspace_root.exists(), str(workspace_root)))
    if not workspace_root.exists():
        errors.append(f"Workspace root does not exist: {workspace_root}.")

    docs_ok = project_root.exists() and (project_root / "docs").exists()
    rows.append((f"{DEFAULT_PROJECT_SUBDIR}/docs", docs_ok, str(project_root)))
    if not docs_ok:
        errors.append(
            "Run /feature-dev-aidd:aidd-init or "
            f"'${{CLAUDE_PLUGIN_ROOT}}/tools/init.sh --target {workspace_root}' to bootstrap."
        )

    print("AIDD Doctor")
    for name, ok, detail in rows:
        print(f"- {name}: {_format_status(ok)} ({detail})")

    if errors:
        print("\nFix:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
