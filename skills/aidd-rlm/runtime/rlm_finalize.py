#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from aidd_runtime import reports_pack, rlm_jsonl_compact, rlm_links_build, rlm_nodes_build, rlm_verify, runtime


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize RLM artifacts after agent-generated nodes.",
    )
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--nodes", help="Override nodes.jsonl path.")
    parser.add_argument("--links", help="Override links.jsonl path.")
    parser.add_argument("--targets", help="Override rlm-targets.json path for link build.")
    parser.add_argument(
        "--bootstrap-if-missing",
        action="store_true",
        help="Bootstrap nodes from manifest when nodes.jsonl is missing/empty before finalize.",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Emit finalize outcome payload as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, project_root = runtime.require_workflow_root()
    ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)

    nodes_path = (
        runtime.resolve_path_for_target(Path(args.nodes), project_root)
        if args.nodes
        else project_root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    )
    links_path = (
        runtime.resolve_path_for_target(Path(args.links), project_root)
        if args.links
        else project_root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    )
    targets_path = (
        runtime.resolve_path_for_target(Path(args.targets), project_root)
        if args.targets
        else None
    )

    payload: dict[str, object] = {
        "status": "blocked",
        "ticket": ticket,
        "bootstrap_attempted": False,
        "finalize_attempted": False,
        "reason_code": "",
        "next_action": "",
        "recovery_path": "",
    }
    nodes_ready = nodes_path.exists() and nodes_path.stat().st_size > 0
    if not nodes_ready and args.bootstrap_if_missing:
        payload["bootstrap_attempted"] = True
        rlm_nodes_build.main(["--ticket", ticket, "--bootstrap"])
        nodes_ready = nodes_path.exists() and nodes_path.stat().st_size > 0
        payload["recovery_path"] = "bootstrap_nodes"
    if not nodes_ready:
        payload["reason_code"] = "rlm_nodes_missing"
        payload["next_action"] = (
            f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_nodes_build.py --bootstrap --ticket {ticket}"
        )
        if args.emit_json:
            print(json.dumps(payload, ensure_ascii=False))
            return 2
        raise SystemExit(f"rlm nodes not found or empty: {nodes_path}")

    payload["finalize_attempted"] = True
    verify_args = ["--ticket", ticket]
    if args.nodes:
        verify_args.extend(["--nodes", str(nodes_path)])
    rlm_verify.main(verify_args)

    links_args = ["--ticket", ticket]
    if args.nodes:
        links_args.extend(["--nodes", str(nodes_path)])
    if targets_path:
        links_args.extend(["--targets", str(targets_path)])
    if args.links:
        links_args.extend(["--output", str(links_path)])
    rlm_links_build.main(links_args)

    compact_args = ["--ticket", ticket]
    if args.nodes:
        compact_args.extend(["--nodes", str(nodes_path)])
    if args.links:
        compact_args.extend(["--links", str(links_path)])
    rlm_jsonl_compact.main(compact_args)

    worklist_args = ["--ticket", ticket, "--refresh-worklist"]
    if args.nodes:
        worklist_args.extend(["--nodes", str(nodes_path)])
    rlm_nodes_build.main(worklist_args)

    pack_args = [
        "--rlm-nodes",
        str(nodes_path),
        "--rlm-links",
        str(links_path),
        "--ticket",
        ticket,
    ]
    reports_pack.main(pack_args)
    payload.update(
        {
            "status": "done",
            "reason_code": "",
            "next_action": "",
            "recovery_path": payload.get("recovery_path") or "finalize",
        }
    )
    if args.emit_json:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
