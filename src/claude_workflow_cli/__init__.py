"""
Claude Workflow CLI package.

Provides Python entrypoints that proxy the existing bootstrap shell scripts
shipped with the ai_driven_dev template.  The package is designed to be
installed via `uv tool install` or `pipx` and then exposes the
`claude-workflow` command.
"""

from importlib import metadata

FALLBACK_VERSION = "0.1.0"


def __getattr__(name: str):
    if name == "__version__":
        try:
            return metadata.version("claude-workflow-cli")
        except metadata.PackageNotFoundError:  # pragma: no cover - during dev
            return FALLBACK_VERSION
    raise AttributeError(name)


__all__ = ["__version__"]
