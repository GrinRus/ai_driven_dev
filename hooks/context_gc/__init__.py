"""Context GC utilities used by hooks and CLI."""

from hooks.hooklib import (  # noqa: F401
    HookContext,
    load_config,
    pretooluse_decision,
    read_hook_context,
    resolve_aidd_root,
    resolve_project_dir,
    sessionstart_additional_context,
    stat_file_bytes,
    userprompt_block,
)
