"""AIDD runtime package for plugin workflows."""

from importlib import metadata

FALLBACK_VERSION = "0.1.0"


def __getattr__(name: str):
    if name == "__version__":
        try:
            return metadata.version("aidd-runtime")
        except metadata.PackageNotFoundError:  # pragma: no cover - during dev
            return FALLBACK_VERSION
    raise AttributeError(name)


__all__ = ["__version__"]
