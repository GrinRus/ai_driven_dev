#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _default_plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_plugin_root() -> Path:
    raw = str(
        os.environ.get("AIDD_PLUGIN_ROOT")
        or os.environ.get("CLAUDE_PLUGIN_ROOT")
        or ""
    ).strip()
    if raw:
        root = Path(raw).expanduser().resolve()
        os.environ["CLAUDE_PLUGIN_ROOT"] = str(root)
        return root
    root = _default_plugin_root()
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(root)
    return root


def _load_payload() -> Dict[str, Any]:
    raw = sys.stdin.read() if sys.stdin and not sys.stdin.closed else ""
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json payload: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _resolve_cwd(payload: Dict[str, Any]) -> Path:
    raw = str(payload.get("cwd") or "").strip()
    if not raw:
        return Path.cwd()
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    return candidate.resolve()


def _hook_commands(event: str) -> List[Tuple[str, Dict[str, str]]]:
    if event == "userprompt":
        return [("context-gc-userprompt.sh", {})]
    if event == "pretooluse":
        return [("context-gc-pretooluse.sh", {})]
    if event == "subagent_stop":
        return [
            ("context-gc-stop.sh", {}),
            ("gate-workflow.sh", {}),
            ("gate-tests.sh", {}),
            ("gate-qa.sh", {}),
            ("format-and-test.sh", {"AIDD_TEST_PROFILE_DEFAULT": "fast"}),
            ("lint-deps.sh", {}),
        ]
    if event == "stop":
        return [
            ("context-gc-stop.sh", {}),
            ("gate-workflow.sh", {}),
            ("gate-tests.sh", {}),
            ("gate-qa.sh", {}),
            ("format-and-test.sh", {"AIDD_TEST_PROFILE_DEFAULT": "targeted"}),
            ("lint-deps.sh", {}),
        ]
    raise ValueError(f"unsupported bridge event: {event}")


def _parse_json_output(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_hook(
    *,
    plugin_root: Path,
    cwd: Path,
    payload: Dict[str, Any],
    hook_name: str,
    extra_env: Dict[str, str],
) -> Dict[str, Any]:
    hook_path = plugin_root / "hooks" / hook_name
    if not hook_path.exists():
        raise FileNotFoundError(f"hook not found: {hook_path}")
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["PYTHONPATH"] = str(plugin_root) if not env.get("PYTHONPATH") else f"{plugin_root}:{env['PYTHONPATH']}"
    env.update(extra_env)
    proc = subprocess.run(
        [str(hook_path)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        check=False,
    )
    parsed = _parse_json_output(proc.stdout)
    result: Dict[str, Any] = {
        "hook": hook_name,
        "returncode": int(proc.returncode),
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "parsed": parsed,
    }
    return result


def _emit(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenCode bridge for existing AIDD hook runtime.")
    parser.add_argument(
        "--event",
        required=True,
        choices=("userprompt", "pretooluse", "stop", "subagent_stop"),
        help="Bridge event type.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = _load_payload()
    plugin_root = _resolve_plugin_root()
    cwd = _resolve_cwd(payload)
    commands = _hook_commands(args.event)
    results: List[Dict[str, Any]] = []
    for hook_name, env in commands:
        result = _run_hook(
            plugin_root=plugin_root,
            cwd=cwd,
            payload=payload,
            hook_name=hook_name,
            extra_env=env,
        )
        results.append(result)
        if int(result["returncode"]) != 0:
            _emit(
                {
                    "event": args.event,
                    "status": "error",
                    "failed_hook": hook_name,
                    "results": results,
                }
            )
            return 1

    if args.event in {"userprompt", "pretooluse"}:
        parsed = dict(results[0].get("parsed") or {})
        parsed["_bridge"] = {
            "event": args.event,
            "hook": results[0].get("hook"),
            "returncode": results[0].get("returncode"),
        }
        _emit(parsed)
        return 0

    _emit(
        {
            "event": args.event,
            "status": "ok",
            "results": [
                {
                    "hook": item.get("hook"),
                    "returncode": item.get("returncode"),
                }
                for item in results
            ],
        }
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
