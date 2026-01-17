from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tools import runtime


def _run_subprocess(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    run_env = {}
    if env:
        run_env.update(env)
    try:
        subprocess.run(cmd, cwd=str(cwd), env=run_env, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"failed to execute {cmd[0]}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"command {' '.join(cmd)} exited with code {exc.returncode};"
            " see logs above for details"
        ) from exc


def run_smoke(verbose: bool) -> None:
    plugin_root = runtime.require_plugin_root()
    script = plugin_root / "dev" / "repo_tools" / "smoke-workflow.sh"
    if not script.exists():
        raise FileNotFoundError(f"smoke script not found at {script}")
    cmd = ["bash", str(script)]
    env = {}
    if verbose:
        env["SMOKE_VERBOSE"] = "1"
    _run_subprocess(cmd, cwd=plugin_root, env=env)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bundled smoke test.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit verbose logs when running the smoke scenario.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_smoke(args.verbose)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
