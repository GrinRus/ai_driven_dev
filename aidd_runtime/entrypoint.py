from __future__ import annotations

import importlib
import inspect
from types import ModuleType
from typing import Any


def export_module(module_name: str, namespace: dict[str, Any]) -> ModuleType:
    """Populate a thin wrapper module with symbols from the explicit runtime module."""

    module = importlib.import_module(module_name)
    for key, value in vars(module).items():
        if key.startswith("__") and key not in {"__all__", "__doc__"}:
            continue
        namespace[key] = value
    return module


def run_main(module_name: str, argv: list[str] | None = None) -> int:
    """Invoke `main()` on the explicit runtime module when present."""

    module = importlib.import_module(module_name)
    main_fn = getattr(module, "main", None)
    if not callable(main_fn):
        return 0
    kwargs: dict[str, Any] = {}
    try:
        signature = inspect.signature(main_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        params = signature.parameters
        if "default_stage" in params and "DEFAULT_STAGE" in vars(module):
            kwargs["default_stage"] = getattr(module, "DEFAULT_STAGE")
        if "description" in params and "DESCRIPTION" in vars(module):
            kwargs["description"] = getattr(module, "DESCRIPTION")
    result = main_fn(argv, **kwargs)
    if isinstance(result, int):
        return result
    return 0
