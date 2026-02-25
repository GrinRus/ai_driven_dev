from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from aidd_runtime.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root
from aidd_runtime import ast_index
from aidd_runtime import runtime


def _format_status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def _check_binary(name: str) -> tuple[bool, str]:
    path = shutil.which(name)
    return (path is not None), (path or "not found in PATH")


def _safe_read_text(path: Path, *, max_bytes: int = 512_000) -> str:
    try:
        if path.stat().st_size > max_bytes:
            with path.open("rb") as handle:
                handle.seek(max(path.stat().st_size - max_bytes, 0))
                return handle.read().decode("utf-8", errors="replace")
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _latest_loop_run_log(project_root: Path) -> Path | None:
    loops_root = project_root / "reports" / "loops"
    if not loops_root.exists():
        return None
    candidates: list[Path] = []
    for path in loops_root.rglob("loop.run.log"):
        if path.is_file():
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0.0, reverse=True)
    return candidates[0]


def _check_loop_observability(project_root: Path) -> tuple[bool, str]:
    loop_log = _latest_loop_run_log(project_root)
    if loop_log is None:
        return True, "no loop.run.log found"
    text = _safe_read_text(loop_log).lower()
    issues: list[str] = []
    has_stream_liveness = "stream_liveness=" in text
    if has_stream_liveness and "active:main_log" in text and "observability_degraded=1" not in text:
        issues.append("active:main_log without observability_degraded marker")

    stream_parts = sorted(loop_log.parent.glob("cli.loop-run.*.stream.*"))
    stream_text = ""
    for path in stream_parts[:4]:
        stream_text += "\n" + _safe_read_text(path)
    merged = f"{text}\n{stream_text.lower()}"
    if '"permissionmode":"default"' in merged or '"permissionmode": "default"' in merged:
        if "reason_code=loop_runner_permissions" not in text:
            issues.append("permissionMode=default observed without reason_code=loop_runner_permissions")

    if issues:
        detail = "; ".join(issues)
        return False, f"{loop_log} ({detail})"
    if has_stream_liveness:
        return True, f"{loop_log} (stream liveness markers present)"
    return True, f"{loop_log} (no stream liveness markers yet)"


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _rollout_scopes(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return ["implement", "review", "qa"]
    scopes = [str(item).strip().lower() for item in raw if str(item).strip()]
    return scopes or ["implement", "review", "qa"]


def _evaluate_ast_rollout_wave2(project_root: Path) -> tuple[bool, bool, str, str]:
    try:
        gates_cfg = runtime.load_gates_config(project_root)
    except Exception as exc:
        return False, False, f"config_error={exc}", ""
    ast_cfg = gates_cfg.get("ast_index") if isinstance(gates_cfg.get("ast_index"), dict) else {}
    rollout_cfg = ast_cfg.get("rollout_wave2") if isinstance(ast_cfg.get("rollout_wave2"), dict) else {}
    enabled = _as_bool(rollout_cfg.get("enabled"), default=False)
    decision_mode = str(rollout_cfg.get("decision_mode") or "advisory").strip().lower() or "advisory"
    enforce = decision_mode in {"hard", "required", "block", "enforce"}
    scopes = _rollout_scopes(rollout_cfg.get("scopes"))
    thresholds_cfg = rollout_cfg.get("thresholds") if isinstance(rollout_cfg.get("thresholds"), dict) else {}
    quality_min = _as_float(thresholds_cfg.get("quality_min"))
    latency_max = _as_int(thresholds_cfg.get("latency_p95_ms_max"))
    fallback_max = _as_float(thresholds_cfg.get("fallback_rate_max"))
    if quality_min is None:
        quality_min = 0.75
    if latency_max is None:
        latency_max = 2500
    if fallback_max is None:
        fallback_max = 0.35

    metrics_artifact_raw = str(
        rollout_cfg.get("metrics_artifact") or "aidd/reports/observability/ast-index.rollout.json"
    ).strip()
    metrics_artifact_path = runtime.resolve_path_for_target(Path(metrics_artifact_raw), project_root)
    metrics_rel = runtime.rel_path(metrics_artifact_path, project_root)

    if not enabled:
        return True, False, (
            f"enabled=false decision_mode={decision_mode} scopes={','.join(scopes)} "
            "status=disabled (wave-1 scope only)"
        ), ""

    if not metrics_artifact_path.exists():
        detail = (
            f"enabled=true decision_mode={decision_mode} scopes={','.join(scopes)} "
            f"artifact={metrics_rel} status=missing_metrics"
        )
        error = (
            "AST wave-2 rollout gate is enforced but metrics artifact is missing: "
            f"{metrics_rel}. Provide quality/latency/fallback metrics or switch decision_mode=advisory."
        )
        return False, enforce, detail, error

    try:
        metrics_payload = json.loads(metrics_artifact_path.read_text(encoding="utf-8"))
    except Exception as exc:
        detail = (
            f"enabled=true decision_mode={decision_mode} scopes={','.join(scopes)} "
            f"artifact={metrics_rel} status=invalid_json ({exc})"
        )
        error = (
            "AST wave-2 rollout gate is enforced but metrics artifact is invalid JSON: "
            f"{metrics_rel}. Fix artifact schema or switch decision_mode=advisory."
        )
        return False, enforce, detail, error

    if not isinstance(metrics_payload, dict):
        detail = (
            f"enabled=true decision_mode={decision_mode} scopes={','.join(scopes)} "
            f"artifact={metrics_rel} status=invalid_payload"
        )
        error = (
            "AST wave-2 rollout gate is enforced but metrics payload is not an object: "
            f"{metrics_rel}. Fix artifact schema or switch decision_mode=advisory."
        )
        return False, enforce, detail, error

    quality = _as_float(metrics_payload.get("quality_score"))
    if quality is None:
        quality = _as_float(metrics_payload.get("quality"))
    latency = _as_int(metrics_payload.get("latency_p95_ms"))
    if latency is None:
        latency = _as_int(metrics_payload.get("latency_ms_p95"))
    fallback_rate = _as_float(metrics_payload.get("fallback_rate"))

    if quality is None or latency is None or fallback_rate is None:
        detail = (
            f"enabled=true decision_mode={decision_mode} scopes={','.join(scopes)} "
            f"artifact={metrics_rel} status=incomplete_metrics"
        )
        error = (
            "AST wave-2 rollout gate is enforced but metrics artifact misses required fields "
            "`quality_score|quality`, `latency_p95_ms`, `fallback_rate`."
        )
        return False, enforce, detail, error

    quality_ok = quality >= quality_min
    latency_ok = latency <= latency_max
    fallback_ok = fallback_rate <= fallback_max
    rollout_ok = quality_ok and latency_ok and fallback_ok
    status = "ready" if rollout_ok else "blocked"
    detail = (
        f"enabled=true decision_mode={decision_mode} scopes={','.join(scopes)} "
        f"quality={quality:.3f}>={quality_min:.3f} latency_p95_ms={latency}<={latency_max} "
        f"fallback_rate={fallback_rate:.3f}<={fallback_max:.3f} status={status} artifact={metrics_rel}"
    )
    error = (
        "AST wave-2 rollout gate thresholds are not satisfied "
        f"(quality_ok={quality_ok}, latency_ok={latency_ok}, fallback_ok={fallback_ok})."
    )
    return rollout_ok, (enforce and not rollout_ok), detail, (error if enforce and not rollout_ok else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIDD install diagnostics.")
    parser.parse_args(argv)

    errors: list[str] = []
    rows: list[tuple[str, bool, str]] = []

    try:
        plugin_root = runtime.require_plugin_root()
        rows.append(("CLAUDE_PLUGIN_ROOT", True, str(plugin_root)))
    except RuntimeError as exc:
        rows.append(("CLAUDE_PLUGIN_ROOT", False, str(exc)))
        errors.append("Set CLAUDE_PLUGIN_ROOT to the plugin install path.")
        plugin_root = None

    snapshot = runtime.capture_plugin_write_safety_snapshot()
    if not snapshot.get("enabled"):
        rows.append(("plugin write-safety", True, "disabled by AIDD_ALLOW_PLUGIN_WRITES=1"))
    elif not snapshot.get("supported"):
        strict_unavailable = runtime.plugin_write_safety_strict_unavailable()
        detail = str(snapshot.get("error") or "git status unavailable")
        if strict_unavailable:
            rows.append(("plugin write-safety", False, detail))
            errors.append(
                "Enable plugin write-safety sentinel (git status must be available) "
                "or unset AIDD_PLUGIN_WRITE_SAFETY_STRICT."
            )
        else:
            rows.append(("plugin write-safety", True, f"degraded (non-git plugin install): {detail}"))
    else:
        dirty_count = len(snapshot.get("entries") or [])
        rows.append(("plugin write-safety", True, f"enabled (baseline dirty entries: {dirty_count})"))

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

    target = Path.cwd().resolve()
    workspace_root, project_root = resolve_project_root(target, DEFAULT_PROJECT_SUBDIR)
    rows.append(("workspace root", workspace_root.exists(), str(workspace_root)))
    if not workspace_root.exists():
        errors.append(f"Workspace root does not exist: {workspace_root}.")

    docs_ok = project_root.exists() and (project_root / "docs").exists()
    rows.append((f"{DEFAULT_PROJECT_SUBDIR}/docs", docs_ok, str(project_root)))
    if not docs_ok:
        errors.append(
            "Run /feature-dev-aidd:aidd-init or "
            f"'python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-init/runtime/init.py' from the workspace root to bootstrap."
        )
    else:
        critical = [
            "AGENTS.md",
            "docs/shared/stage-lexicon.md",
            "docs/loops/template.loop-pack.md",
            "docs/tasklist/template.md",
        ]
        for rel in critical:
            target = project_root / rel
            ok = target.exists()
            rows.append((f"{DEFAULT_PROJECT_SUBDIR}/{rel}", ok, str(target)))
            if not ok:
                errors.append(f"Missing critical artifact: {target}")

    loop_obs_ok, loop_obs_detail = _check_loop_observability(project_root)
    rows.append(("loop stream observability", loop_obs_ok, loop_obs_detail))
    if not loop_obs_ok:
        errors.append(
            "Loop stream observability diagnostics failed: "
            "ensure stream_liveness emits observability_degraded markers and loop_runner_permissions precedence."
        )

    try:
        ast_cfg = ast_index.load_ast_index_config(project_root)
        ast_probe = ast_index.probe_readiness(project_root, ast_cfg)
    except Exception as exc:
        ast_cfg = ast_index.AstIndexConfig()
        ast_probe = {
            "mode": ast_cfg.mode,
            "required": ast_cfg.required,
            "available": False,
            "index_ready": False,
            "reason_code": f"ast_index_probe_error:{exc}",
            "version": "",
            "binary": ast_cfg.binary,
        }
    ast_required = bool(ast_probe.get("required"))
    ast_available = bool(ast_probe.get("available"))
    ast_index_ready = bool(ast_probe.get("index_ready"))
    ast_reason = str(ast_probe.get("reason_code") or "").strip() or "ok"
    ast_version = str(ast_probe.get("version") or "").strip()
    ast_detail = (
        f"mode={ast_probe.get('mode')} required={ast_required} "
        f"available={ast_available} index_ready={ast_index_ready} "
        f"binary={ast_probe.get('binary')} reason={ast_reason}"
    )
    if ast_version:
        ast_detail += f" version={ast_version}"

    ast_ok = (ast_available and ast_index_ready) or (not ast_required)
    rows.append(("ast-index readiness", ast_ok, ast_detail))
    if ast_required and not (ast_available and ast_index_ready):
        errors.append(
            "ast-index is required by config but not ready. Install/index ast-index "
            "or change aidd/config/conventions.json + aidd/config/gates.json to optional mode."
        )

    ast_rollout_ok, ast_rollout_block, ast_rollout_detail, ast_rollout_error = _evaluate_ast_rollout_wave2(project_root)
    rows.append(("ast-index wave-2 rollout", ast_rollout_ok, ast_rollout_detail))
    if ast_rollout_block and ast_rollout_error:
        errors.append(ast_rollout_error)

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
