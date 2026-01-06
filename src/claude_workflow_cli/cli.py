from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from importlib import metadata, resources
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from claude_workflow_cli.feature_ids import (
    FeatureIdentifiers,
    read_identifiers,
    resolve_identifiers,
    resolve_project_root as resolve_aidd_root,
    write_identifiers,
)

from claude_workflow_cli import progress as _progress
from claude_workflow_cli.tools.analyst_guard import (
    AnalystValidationError,
    load_settings as _load_analyst_settings,
    validate_prd as _validate_analyst_prd,
)
from claude_workflow_cli.tools.research_guard import (
    ResearchValidationError,
    load_settings as _load_research_settings,
    validate_research as _validate_research,
)
from claude_workflow_cli.tools.researcher_context import (
    ResearcherContextBuilder,
    _DEFAULT_GRAPH_LIMIT,
    _parse_keywords as _research_parse_keywords,
    _parse_langs as _research_parse_langs,
    _parse_graph_engine as _research_parse_graph_engine,
    _parse_graph_filter as _research_parse_graph_filter,
    _parse_notes as _research_parse_notes,
    _parse_paths as _research_parse_paths,
)
from claude_workflow_cli.tools import plan_review_gate as _plan_review_gate
from claude_workflow_cli.tools import prd_review as _prd_review
from claude_workflow_cli.tools import prd_review_gate as _prd_review_gate
from claude_workflow_cli.tools import qa_agent as _qa_agent
from claude_workflow_cli.context_gc import (
    precompact_snapshot as _context_precompact,
    pretooluse_guard as _context_pretooluse,
    sessionstart_inject as _context_sessionstart,
    userprompt_guard as _context_userprompt,
)
from claude_workflow_cli.resources import (
    DEFAULT_PROJECT_SUBDIR,
    resolve_project_root as resolve_workspace_root,
)


PAYLOAD_PACKAGE = "claude_workflow_cli.data"

try:
    VERSION = metadata.version("claude-workflow-cli")
except metadata.PackageNotFoundError:  # pragma: no cover - editable installs
    VERSION = "0.1.0"

DEFAULT_RELEASE_REPO = os.getenv("CLAUDE_WORKFLOW_RELEASE_REPO", "ai-driven-dev/ai_driven_dev")
CACHE_ENV = "CLAUDE_WORKFLOW_CACHE"
HTTP_TIMEOUT = int(os.getenv("CLAUDE_WORKFLOW_HTTP_TIMEOUT", "30"))
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "claude-workflow"
DEFAULT_REVIEWER_MARKER = "reports/reviewer/{ticket}.json"
DEFAULT_REVIEWER_FIELD = "tests"
DEFAULT_REVIEWER_REQUIRED = ("required",)
DEFAULT_REVIEWER_OPTIONAL = ("optional", "skipped", "not-required")
DEFAULT_QA_TEST_COMMAND = [["bash", "hooks/format-and-test.sh"]]
WORKSPACE_ROOT_DIRS = {".claude", ".claude-plugin"}
VALID_STAGES = {
    "idea",
    "research",
    "plan",
    "review-plan",
    "review-prd",
    "tasklist",
    "implement",
    "review",
    "qa",
}


def _resolve_roots(raw_target: Path, *, create: bool = False) -> tuple[Path, Path]:
    workspace_root, project_root = resolve_workspace_root(raw_target, DEFAULT_PROJECT_SUBDIR)
    if project_root.exists():
        return workspace_root, project_root
    if create:
        project_root.mkdir(parents=True, exist_ok=True)
        return workspace_root, project_root
    if not workspace_root.exists():
        raise FileNotFoundError(f"workspace directory {workspace_root} does not exist")
    raise FileNotFoundError(
        f"workflow not found at {project_root}. Initialise via "
        f"'claude-workflow init --target {workspace_root}' "
        f"(templates install into ./{DEFAULT_PROJECT_SUBDIR})."
    )


def _require_workflow_root(raw_target: Path) -> tuple[Path, Path]:
    workspace_root, project_root = _resolve_roots(raw_target, create=False)
    if (project_root / ".claude").exists() or (workspace_root / ".claude").exists():
        return workspace_root, project_root
    raise FileNotFoundError(
        f"workflow files not found at {project_root}/.claude or {workspace_root}/.claude; "
        f"bootstrap via 'claude-workflow init --target {workspace_root}' "
        f"(templates install into ./{DEFAULT_PROJECT_SUBDIR})."
    )


def _normalize_stage(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _slug_to_title(slug: str) -> str:
    parts = [chunk for chunk in slug.replace("_", "-").split("-") if chunk]
    if not parts:
        return slug
    return " ".join(part.capitalize() for part in parts)


def _render_tasklist_heading(original: str, title: str) -> str:
    lines = original.splitlines()
    idx = next((i for i, line in enumerate(lines) if line.strip()), None)
    if idx is None:
        return f"# Tasklist — {title}\n"
    first = lines[idx].strip()
    if first.lower().startswith("# tasklist"):
        lines[idx] = f"# Tasklist — {title}"
    else:
        lines.insert(idx, f"# Tasklist — {title}")
    return "\n".join(lines).rstrip() + "\n"


def _maybe_migrate_tasklist(root: Path, ticket: str, slug_hint: Optional[str]) -> None:
    legacy = root / "tasklist.md"
    if not legacy.exists():
        return
    destination = root / "docs" / "tasklist" / f"{ticket}.md"
    if destination.exists():
        return
    try:
        display_name = slug_hint or ticket
        title = _slug_to_title(display_name)
        slug_value = slug_hint or ticket
        today = dt.date.today().isoformat()
        legacy_text = legacy.read_text(encoding="utf-8")
        body = _render_tasklist_heading(legacy_text, title)
        front_matter = (
            "---\n"
            f"Ticket: {ticket}\n"
            f"Slug hint: {slug_value}\n"
            f"Feature: {title}\n"
            "Status: draft\n"
            f"PRD: docs/prd/{ticket}.prd.md\n"
            f"Plan: docs/plan/{ticket}.md\n"
            f"Research: docs/research/{ticket}.md\n"
            f"Updated: {today}\n"
            "---\n\n"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(front_matter + body, encoding="utf-8")
        legacy.unlink()
        print(f"[tasklist] migrated legacy tasklist.md to {destination}", file=sys.stderr)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"[tasklist] failed to migrate legacy tasklist.md: {exc}", file=sys.stderr)


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _ensure_active_ticket(root: Path, *, dry_run: bool) -> tuple[bool, Optional[str]]:
    docs_dir = root / "docs"
    slug_file = docs_dir / ".active_feature"
    ticket_file = docs_dir / ".active_ticket"

    slug_value = _read_text(slug_file)
    ticket_value_raw = _read_text(ticket_file)
    ticket_value = ticket_value_raw.strip() if ticket_value_raw else ""

    if ticket_value:
        return False, ticket_value

    if not slug_value:
        return False, None

    slug_value = slug_value.strip()
    if not slug_value:
        return False, None

    if dry_run:
        print(f"[dry-run] write {ticket_file} ← {slug_value}")
    else:
        ticket_file.write_text(slug_value + "\n", encoding="utf-8")
        print(f"[migrate] created {ticket_file} from .active_feature")
    return True, slug_value


def _migrate_tasklist_front_matter(path: Path, *, dry_run: bool) -> bool:
    text = _read_text(path)
    if text is None:
        return False

    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return False

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return False

    front = lines[1:end_idx]
    body = lines[end_idx + 1 :]

    ticket_line = next((ln for ln in front if ln.lower().startswith("ticket:")), None)
    slug_hint_line = next((ln for ln in front if ln.lower().startswith("slug hint:")), None)
    feature_line = next((ln for ln in front if ln.lower().startswith("feature:")), None)

    filename_ticket = path.stem
    feature_value = ""
    if feature_line:
        feature_value = feature_line.split(":", 1)[1].strip()

    updated = False
    new_front: list[str] = []

    def append_ticket_block() -> None:
        nonlocal ticket_line, slug_hint_line, updated
        if ticket_line is None:
            ticket_line = f"Ticket: {filename_ticket}"
            new_front.append(ticket_line)
            updated = True
        else:
            new_front.append(ticket_line)
        if slug_hint_line is None:
            slug_value = feature_value or filename_ticket
            slug_hint_line_local = f"Slug hint: {slug_value}"
            new_front.append(slug_hint_line_local)
            slug_hint_line = slug_hint_line_local
            updated = True
        else:
            new_front.append(slug_hint_line)

    inserted = False
    for line in front:
        if line.lower().startswith("ticket:"):
            new_front.append(line)
            inserted = True
            continue
        if line.lower().startswith("slug hint:"):
            if not inserted and ticket_line is None:
                new_front.append(f"Ticket: {filename_ticket}")
                inserted = True
                updated = True
            new_front.append(line)
            continue
        if line.lower().startswith("feature:") and not inserted:
            append_ticket_block()
            inserted = True
        new_front.append(line)

    if not inserted:
        append_ticket_block()

    if not updated:
        return False

    new_lines = ["---", *new_front, "---", *body]
    new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
    if dry_run:
        print(f"[dry-run] update front-matter in {path}")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"[migrate] updated front-matter in {path}")
    return True


def _migrate_tasklists(root: Path, *, dry_run: bool) -> int:
    tasklist_dir = root / "docs" / "tasklist"
    if not tasklist_dir.is_dir():
        return 0
    updated = 0
    for candidate in sorted(tasklist_dir.glob("*.md")):
        if _migrate_tasklist_front_matter(candidate, dry_run=dry_run):
            updated += 1
    return updated


def _resolve_slug_for_tasklist(root: Path, provided: Optional[str]) -> str:
    if provided:
        return provided.strip()
    active_file = root / "docs" / ".active_feature"
    if active_file.exists():
        raw = active_file.read_text(encoding="utf-8").strip()
        if raw:
            return raw
    plan_dir = root / "docs" / "plan"
    if plan_dir.exists():
        plans = sorted(path.stem for path in plan_dir.glob("*.md"))
        if len(plans) == 1:
            return plans[0]
    raise SystemExit("Cannot determine feature slug: use --slug or populate docs/.active_feature.")


def _migrate_legacy_tasklist(root: Path, slug: str, force: bool) -> int:
    legacy = root / "tasklist.md"
    if not legacy.exists():
        print("[tasklist] legacy tasklist.md not found; nothing to migrate.")
        return 0

    destination = root / "docs" / "tasklist" / f"{slug}.md"
    if destination.exists() and not force:
        print(f"[tasklist] destination {destination} already exists. Use --force to overwrite.")
        return 1

    title = _slug_to_title(slug)
    today = dt.date.today().isoformat()
    legacy_text = legacy.read_text(encoding="utf-8")
    body = _render_tasklist_heading(legacy_text, title)
    front_matter = (
        "---\n"
        f"Ticket: {slug}\n"
        f"Slug hint: {slug}\n"
        f"Feature: {title}\n"
        "Status: draft\n"
        f"PRD: docs/prd/{slug}.prd.md\n"
        f"Plan: docs/plan/{slug}.md\n"
        f"Research: docs/research/{slug}.md\n"
        f"Updated: {today}\n"
        "---\n\n"
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(front_matter + body, encoding="utf-8")
    legacy.unlink()

    feature_file = root / "docs" / ".active_feature"
    feature_file.parent.mkdir(parents=True, exist_ok=True)
    feature_file.write_text(slug + "\n", encoding="utf-8")

    ticket_file = root / "docs" / ".active_ticket"
    ticket_file.parent.mkdir(parents=True, exist_ok=True)
    ticket_file.write_text(slug + "\n", encoding="utf-8")

    print(f"[tasklist] migrated to {destination}")
    return 0


class PayloadError(RuntimeError):
    """Raised when the payload cannot be prepared for use."""


def _cache_root(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    env_override = os.getenv(CACHE_ENV)
    if env_override:
        return Path(env_override).expanduser()
    return DEFAULT_CACHE_DIR


def _github_token() -> str | None:
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    return token.strip() if token else None


def _github_headers(token: str | None, *, accept: str = "application/vnd.github+json") -> Dict[str, str]:
    headers = {
        "User-Agent": f"claude-workflow-cli/{VERSION}",
        "Accept": accept,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_get_json(url: str, token: str | None) -> Dict:
    request = urllib.request.Request(url, headers=_github_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network errors
        raise PayloadError(f"GitHub API request failed ({exc.code} {exc.reason}) for {url}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network errors
        raise PayloadError(f"GitHub API request failed: {exc.reason}") from exc
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise PayloadError(f"Failed to parse GitHub API response from {url}: {exc}") from exc


def _download_file(url: str, destination: Path, token: str | None) -> None:
    request = urllib.request.Request(url, headers=_github_headers(token, accept="application/octet-stream"))
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response, destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network errors
        raise PayloadError(f"Download failed ({exc.code} {exc.reason}) for {url}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network errors
        raise PayloadError(f"Download failed for {url}: {exc.reason}") from exc


def _parse_release_spec(spec: str) -> Tuple[str, str]:
    if "@" in spec:
        repo, tag = spec.split("@", 1)
    else:
        repo = DEFAULT_RELEASE_REPO
        tag = spec
    if not repo or "/" not in repo:
        raise PayloadError("Release specification must include owner/repo (set CLAUDE_WORKFLOW_RELEASE_REPO or use owner/repo@tag).")
    return repo, tag or "latest"


def _fetch_release_data(repo: str, tag: str, token: str | None) -> Dict:
    owner, name = repo.split("/", 1)
    if tag.lower() == "latest":
        url = f"https://api.github.com/repos/{owner}/{name}/releases/latest"
    else:
        url = f"https://api.github.com/repos/{owner}/{name}/releases/tags/{tag}"
    return _http_get_json(url, token)


def _select_payload_asset(release: Dict) -> Dict:
    assets = release.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith(".zip") and "payload" in name:
            return asset
    raise PayloadError("Release does not contain a payload .zip asset.")


def _extract_payload_archive(archive_path: Path, payload_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="claude_payload_") as temp_dir:
        temp_path = Path(temp_dir)
        with zipfile.ZipFile(archive_path) as zip_file:
            zip_file.extractall(temp_path)
        manifest_candidates = sorted(temp_path.rglob("manifest.json"), key=lambda p: len(p.relative_to(temp_path).parts))
        if not manifest_candidates:
            raise PayloadError("Downloaded payload archive does not contain manifest.json.")
        payload_source = manifest_candidates[0].parent
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        shutil.copytree(payload_source, payload_dir)


def _ensure_remote_payload(spec: str, cache_override: str | None = None) -> Path:
    repo, requested_tag = _parse_release_spec(spec)
    token = _github_token()
    release = _fetch_release_data(repo, requested_tag, token)
    tag = release.get("tag_name") or requested_tag or "latest"
    cache_root = _cache_root(cache_override)
    cache_root.mkdir(parents=True, exist_ok=True)
    repo_slug = repo.replace("/", "__")
    release_cache_dir = cache_root / repo_slug / tag
    payload_dir = release_cache_dir / "payload"
    asset = _select_payload_asset(release)
    archive_path = release_cache_dir / asset["name"]

    # Try cached payload first
    if payload_dir.exists():
        try:
            _load_manifest(payload_dir)
            return payload_dir
        except PayloadError:
            shutil.rmtree(payload_dir, ignore_errors=True)

    # Reuse cached archive if present
    if archive_path.exists():
        try:
            _extract_payload_archive(archive_path, payload_dir)
            _load_manifest(payload_dir)
            return payload_dir
        except PayloadError:
            archive_path.unlink(missing_ok=True)

    release_cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"[claude-workflow] downloading payload {repo}@{tag} ({asset['name']})")
    with tempfile.NamedTemporaryFile(prefix="claude_payload_", suffix=".zip", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        _download_file(asset["browser_download_url"], temp_path, token)
        shutil.move(str(temp_path), archive_path)
    finally:
        temp_path.unlink(missing_ok=True)

    _extract_payload_archive(archive_path, payload_dir)
    _load_manifest(payload_dir)
    metadata_path = release_cache_dir / "release.json"
    metadata_path.write_text(
        json.dumps(
            {"repo": repo, "tag": tag, "asset": asset.get("name"), "download_url": asset.get("browser_download_url")},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload_dir


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(payload_path: Path) -> Dict[str, Dict]:
    manifest_path = payload_path / "manifest.json"
    if not manifest_path.exists():
        raise PayloadError(f"Payload manifest not found at {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PayloadError(f"Failed to parse payload manifest: {exc}") from exc

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise PayloadError("Payload manifest does not contain any files.")

    entries: Dict[str, Dict] = {}
    for entry in files:
        rel = entry.get("path")
        if not rel:
            raise PayloadError("Payload manifest entry missing path.")
        if rel in entries:
            raise PayloadError(f"Duplicate entry in payload manifest: {rel}")
        file_path = payload_path / rel
        if not file_path.exists():
            raise PayloadError(f"Payload file listed in manifest is missing: {rel}")
        if rel == "manifest.json":
            # Self-referential entry: skip checksum validation to avoid infinite hash churn.
            entries[rel] = entry
            continue
        expected_hash = entry.get("sha256")
        actual_hash = _hash_file(file_path)
        if expected_hash != actual_hash:
            raise PayloadError(f"Checksum mismatch for {rel}: manifest has {expected_hash}, actual is {actual_hash}")
        entries[rel] = entry

    extra_files = []
    for path in payload_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(payload_path).as_posix()
        if rel == "manifest.json":
            continue
        if rel not in entries:
            extra_files.append(rel)
    if extra_files:
        raise PayloadError(f"Payload contains files missing from manifest: {', '.join(sorted(extra_files))}")
    return entries


def _filter_manifest_for_entries(
    entries: Iterable[Tuple[Path, Path]], manifest: Dict[str, Dict]
) -> Tuple[Dict[str, Dict], List[str]]:
    relevant: Dict[str, Dict] = {}
    unmanaged: List[str] = []
    for _, rel_path in entries:
        rel = rel_path.as_posix()
        entry = manifest.get(rel)
        if entry:
            relevant[rel] = entry
        else:
            unmanaged.append(rel)
    unexpected = [item for item in unmanaged if item != "manifest.json"]
    if unexpected:
        raise PayloadError(
            "Payload entries missing from manifest: " + ", ".join(sorted(unexpected))
        )
    return relevant, unmanaged


def _report_manifest_diff(
    destination_root: Path, manifest_entries: Dict[str, Dict], *, prefix: str
) -> Tuple[List[str], List[str]]:
    new_files: List[str] = []
    changed_files: List[str] = []
    for rel, entry in manifest_entries.items():
        destination = destination_root / rel
        if not destination.exists():
            new_files.append(rel)
            continue
        dest_hash = _hash_file(destination)
        if dest_hash != entry.get("sha256"):
            changed_files.append(rel)

    if new_files or changed_files:
        print(f"[claude-workflow] manifest diff for {prefix}:")
        if new_files:
            print(f"  + new files ({len(new_files)}):")
            for rel in new_files[:10]:
                print(f"    {rel}")
            if len(new_files) > 10:
                print("    …")
        if changed_files:
            print(f"  ~ changed files ({len(changed_files)}):")
            for rel in changed_files[:10]:
                print(f"    {rel}")
            if len(changed_files) > 10:
                print("    …")
    else:
        print(f"[claude-workflow] manifest diff for {prefix}: no changes required.")

    return new_files, changed_files

@contextmanager
def _payload_root(
    release: str | None = None, cache_dir: str | None = None
) -> Iterable[Path]:
    """
    Yields a concrete filesystem path that contains the bundled bootstrap
    payload (shell scripts, templates, etc.).  The context manager
    ensures compatibility with zipped installations where resources can only be
    accessed via a temporary directory.
    """
    if release:
        try:
            yield _ensure_remote_payload(release, cache_dir)
            return
        except PayloadError as exc:
            print(
                f"[claude-workflow] failed to download payload from release '{release}': {exc}; falling back to bundled templates.",
                file=sys.stderr,
            )
        except Exception as exc:  # pragma: no cover - unexpected failure
            print(
                f"[claude-workflow] unexpected error while downloading payload from release '{release}': {exc}; falling back to bundled templates.",
                file=sys.stderr,
            )
    payload = resources.files(PAYLOAD_PACKAGE) / "payload"
    with resources.as_file(payload) as resolved:
        yield Path(resolved)


def _run_subprocess(
    cmd: List[str], *, cwd: Path, env: dict[str, str] | None = None
) -> int:
    run_env = os.environ.copy()
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
    return 0


def _run_init(
    target: Path,
    extra_args: List[str] | None = None,
) -> None:
    extra_args = extra_args or []
    workspace_root, project_root = _resolve_roots(target, create=True)
    current_version = _read_template_version(project_root)
    if current_version and current_version != VERSION:
        print(
            f"[claude-workflow] existing template version {current_version} detected;"
            f" CLI {VERSION} will refresh files."
        )

    with _payload_root() as payload_path:
        template_root = payload_path / DEFAULT_PROJECT_SUBDIR
        script = template_root / "init-claude-workflow.sh"
        if not script.exists():
            raise FileNotFoundError(f"bootstrap script not found at {script}")
        env = {"CLAUDE_TEMPLATE_DIR": str(template_root)}
        cmd = ["bash", str(script), *extra_args]
        _run_subprocess(cmd, cwd=project_root, env=env)
    _write_template_version(project_root)


def _run_smoke(verbose: bool) -> None:
    with _payload_root() as payload_path:
        script = payload_path / "smoke-workflow.sh"
        if not script.exists():
            manifest = _load_manifest(payload_path)
            manifest_prefix = _detect_manifest_prefix(manifest)
            if manifest_prefix:
                candidate = payload_path / manifest_prefix / "smoke-workflow.sh"
                if candidate.exists():
                    script = candidate
        if not script.exists():
            raise FileNotFoundError(f"smoke script not found at {script}")
        cmd = ["bash", str(script)]
        env = {}
        if verbose:
            env["SMOKE_VERBOSE"] = "1"
        # smoke script handles its own temp directory; run from payload root
        _run_subprocess(cmd, cwd=script.parent, env=env)


def _init_command(args: argparse.Namespace) -> None:
    script_args = ["--commit-mode", args.commit_mode]
    if args.enable_ci:
        script_args.append("--enable-ci")
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    _run_init(Path(args.target).resolve(), script_args)


def _smoke_command(args: argparse.Namespace) -> None:
    _run_smoke(args.verbose)


def _set_active_stage_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    stage = _normalize_stage(args.stage)
    if not args.allow_custom and stage not in VALID_STAGES:
        valid = ", ".join(sorted(VALID_STAGES))
        print(f"[stage] invalid stage '{stage}'. Allowed: {valid}.", file=sys.stderr)
        return 2
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    stage_path = docs_dir / ".active_stage"
    stage_path.write_text(stage + "\n", encoding="utf-8")
    print(f"active stage: {stage}")
    return 0


def _set_active_feature_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    write_identifiers(
        root,
        ticket=args.ticket,
        slug_hint=args.slug_note,
        scaffold_prd_file=not args.skip_prd_scaffold,
    )
    identifiers = read_identifiers(root)
    resolved_slug_hint = identifiers.slug_hint or identifiers.ticket or args.ticket

    print(f"active feature: {args.ticket}")
    _maybe_migrate_tasklist(root, args.ticket, resolved_slug_hint)

    config_path: Optional[Path] = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (root / config_path).resolve()
        else:
            config_path = config_path.resolve()

    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(args.ticket, slug_hint=resolved_slug_hint)
    scope = builder.extend_scope(
        scope,
        extra_paths=_research_parse_paths(args.paths),
        extra_keywords=_research_parse_keywords(args.keywords),
    )
    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(root).as_posix()
    print(f"[researcher] targets saved to {rel_targets} ({len(scope.paths)} paths, {len(scope.docs)} docs)")
    return 0


def _migrate_ticket_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    if not root.exists():
        print(f"[error] target directory {root} does not exist", file=sys.stderr)
        return 1

    created_ticket, ticket_value = _ensure_active_ticket(root, dry_run=args.dry_run)
    tasklist_updates = _migrate_tasklists(root, dry_run=args.dry_run)

    if args.dry_run:
        print("[dry-run] migration completed (no files modified).")
        return 0

    if created_ticket:
        print(f"[summary] aidd/docs/.active_ticket set to '{ticket_value}'.")
    if tasklist_updates:
        print(f"[summary] updated {tasklist_updates} tasklist front-matter file(s).")
    if not created_ticket and tasklist_updates == 0:
        print("[summary] nothing to migrate — repository already uses ticket-first layout.")
    return 0


def _migrate_tasklist_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    try:
        slug = _resolve_slug_for_tasklist(root, args.slug)
    except SystemExit as exc:
        message = str(exc)
        if message:
            print(message, file=sys.stderr)
        return 1
    return _migrate_legacy_tasklist(root, slug, args.force)


def _prd_review_command(args: argparse.Namespace) -> int:
    return _prd_review.run(args)


def _plan_review_gate_command(args: argparse.Namespace) -> int:
    return _plan_review_gate.run_gate(args)


def _prd_review_gate_command(args: argparse.Namespace) -> int:
    return _prd_review_gate.run_gate(args)


def _researcher_context_command(args: argparse.Namespace) -> int:
    from claude_workflow_cli.tools import researcher_context as _researcher_context

    argv = args.forward_args or []
    return _researcher_context.main(argv)


def _context_gc_command(args: argparse.Namespace) -> None:
    mode = args.mode
    if mode == "precompact":
        _context_precompact.main()
    elif mode == "sessionstart":
        _context_sessionstart.main()
    elif mode == "pretooluse":
        _context_pretooluse.main()
    elif mode == "userprompt":
        _context_userprompt.main()


def _analyst_check_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    settings = _load_analyst_settings(target)
    try:
        summary = _validate_analyst_prd(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
            require_ready_override=False if args.no_ready_required else None,
            allow_blocked_override=True if args.allow_blocked else None,
            min_questions_override=args.min_questions,
        )
    except AnalystValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    if summary.status is None:
        print("[claude-workflow] analyst gate disabled; nothing to validate.")
        return

    label = _format_ticket_label(context, fallback=ticket)
    print(f"[claude-workflow] analyst dialog ready for `{label}` "
          f"(status: {summary.status}, questions: {summary.question_count}).")


def _research_check_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    settings = _load_research_settings(target)
    try:
        summary = _validate_research(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
        )
    except ResearchValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    if summary.status is None:
        if summary.skipped_reason:
            print(f"[claude-workflow] research gate skipped ({summary.skipped_reason}).")
        else:
            print("[claude-workflow] research gate disabled; nothing to validate.")
        return

    label = _format_ticket_label(context, fallback=ticket)
    details = [f"status: {summary.status}"]
    if summary.path_count is not None:
        details.append(f"paths: {summary.path_count}")
    if summary.age_days is not None:
        details.append(f"age: {summary.age_days}d")
    print(f"[claude-workflow] research gate OK for `{label}` ({', '.join(details)}).")


def _research_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())

    ticket, feature_context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )

    config_path: Optional[Path] = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (target / config_path).resolve()
        else:
            config_path = config_path.resolve()
    builder = ResearcherContextBuilder(
        target,
        config_path=config_path,
        paths_relative=getattr(args, "paths_relative", None),
    )
    scope = builder.build_scope(ticket, slug_hint=feature_context.slug_hint)
    scope = builder.extend_scope(
        scope,
        extra_paths=_research_parse_paths(args.paths),
        extra_keywords=_research_parse_keywords(args.keywords),
        extra_notes=_research_parse_notes(getattr(args, "notes", None), target),
    )
    _, _, search_roots = builder.describe_targets(scope)

    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(target).as_posix()
    base_root = builder.workspace_root if builder.paths_relative_mode == "workspace" else builder.root
    base_label = f"{builder.paths_relative_mode}:{base_root}"
    print(
        f"[claude-workflow] researcher targets saved to {rel_targets} "
        f"({len(scope.paths)} paths, {len(scope.docs)} docs; base={base_label})."
    )

    if args.targets_only:
        return

    languages = _research_parse_langs(getattr(args, "langs", None))
    graph_languages = _research_parse_langs(getattr(args, "graph_langs", None))
    graph_engine = _research_parse_graph_engine(getattr(args, "graph_engine", None))
    auto_filter = "|".join(scope.keywords + [scope.ticket])
    graph_filter = _research_parse_graph_filter(getattr(args, "graph_filter", None), fallback=auto_filter)
    raw_limit = getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT)
    try:
        graph_limit = int(raw_limit)
    except (TypeError, ValueError):
        graph_limit = _DEFAULT_GRAPH_LIMIT
    if graph_limit <= 0:
        graph_limit = _DEFAULT_GRAPH_LIMIT

    collected_context = builder.collect_context(scope, limit=args.limit)
    if args.deep_code:
        code_index, reuse_candidates = builder.collect_deep_context(
            scope,
            roots=search_roots,
            keywords=scope.keywords,
            languages=languages,
            reuse_only=args.reuse_only,
            limit=args.limit,
        )
        collected_context["code_index"] = code_index
        collected_context["reuse_candidates"] = reuse_candidates
        collected_context["deep_mode"] = True
    else:
        collected_context["deep_mode"] = False
    if args.call_graph:
        graph = builder.collect_call_graph(
            scope,
            roots=search_roots,
            languages=graph_languages or languages or ["kt", "kts", "java"],
            engine_name=graph_engine,
            graph_filter=graph_filter,
            graph_limit=graph_limit,
        )
        collected_context["call_graph"] = graph.get("edges", [])
        collected_context["import_graph"] = graph.get("imports", [])
        collected_context["call_graph_engine"] = graph.get("engine", graph_engine)
        collected_context["call_graph_supported_languages"] = graph.get("supported_languages", [])
        if graph.get("edges_full") is not None:
            full_path = Path(args.output or f"reports/research/{ticket}-call-graph-full.json")
            if not full_path.is_absolute():
                full_path = target / full_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_payload = {"edges": graph.get("edges_full", []), "imports": graph.get("imports", [])}
            full_path.write_text(json.dumps(full_payload, indent=2), encoding="utf-8")
            collected_context["call_graph_full_path"] = os.path.relpath(full_path, target)
        collected_context["call_graph_filter"] = graph_filter
        collected_context["call_graph_limit"] = graph_limit
        if graph.get("warning"):
            collected_context["call_graph_warning"] = graph.get("warning")
    else:
        collected_context["call_graph"] = []
        collected_context["import_graph"] = []
        collected_context["call_graph_engine"] = graph_engine
        collected_context["call_graph_supported_languages"] = []
    collected_context["auto_mode"] = bool(getattr(args, "auto", False))
    match_count = len(collected_context["matches"])
    if match_count == 0:
        print(
            f"[claude-workflow] researcher found 0 matches for `{ticket}` — зафиксируйте baseline и статус pending в docs/research/{ticket}.md."
        )
        if (
            builder.paths_relative_mode == "aidd"
            and builder.workspace_root != builder.root
            and any((builder.workspace_root / name).exists() for name in ("src", "services", "modules", "apps"))
        ):
            print(
                "[claude-workflow] hint: включите workspace-relative paths (--paths-relative workspace) "
                "или добавьте ../paths — под aidd/ нет поддерживаемых файлов, но в workspace есть код.",
                file=sys.stderr,
            )
    if args.dry_run:
        print(json.dumps(collected_context, indent=2, ensure_ascii=False))
        return

    output = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, collected_context, output=output)
    rel_output = output_path.relative_to(target).as_posix()
    reuse_count = len(collected_context.get("reuse_candidates") or []) if args.deep_code else 0
    call_edges = len(collected_context.get("call_graph") or []) if args.call_graph else 0
    message = f"[claude-workflow] researcher context saved to {rel_output} ({match_count} matches; base={base_label}"
    if args.deep_code:
        message += f", {reuse_count} reuse candidates"
    if args.call_graph:
        message += f", {call_edges} call edges"
    message += ")."
    print(message)

    if args.no_template:
        return

    template_overrides: dict[str, str] = {}
    if match_count == 0:
        template_overrides["{{empty-context-note}}"] = "Контекст пуст: требуется baseline после автоматического запуска."
        template_overrides["{{positive-patterns}}"] = "TBD — данные появятся после baseline."
        template_overrides["{{negative-patterns}}"] = "TBD — сначала найдите артефакты."
    if scope.manual_notes:
        template_overrides["{{manual-note}}"] = "; ".join(scope.manual_notes[:3])

    doc_path, created = _ensure_research_doc(
        target,
        ticket,
        slug_hint=feature_context.slug_hint,
        template_overrides=template_overrides or None,
    )
    if not doc_path:
        print("[claude-workflow] research summary template not found; skipping materialisation.")
        return
    rel_doc = doc_path.relative_to(target).as_posix()
    if created:
        print(f"[claude-workflow] research summary created at {rel_doc}.")
    else:
        print(f"[claude-workflow] research summary already exists at {rel_doc}.")


def _reviewer_tests_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())

    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )

    reviewer_cfg = _reviewer_gate_config(target)
    marker_template = str(
        reviewer_cfg.get("marker")
        or reviewer_cfg.get("tests_marker")
        or DEFAULT_REVIEWER_MARKER
    )
    marker_path = _reviewer_marker_path(target, marker_template, ticket, context.slug_hint)
    rel_marker = marker_path.relative_to(target).as_posix()

    if args.clear:
        if marker_path.exists():
            marker_path.unlink()
            print(f"[claude-workflow] reviewer marker cleared ({rel_marker}).")
        else:
            print(f"[claude-workflow] reviewer marker not found at {rel_marker}.")
        return

    status = (args.status or "required").strip().lower()
    alias_map = {"skip": "skipped"}
    status = alias_map.get(status, status)

    def _extract_values(primary_key: str, legacy_key: str, fallback: Sequence[str]) -> list[str]:
        raw = reviewer_cfg.get(primary_key)
        if raw is None:
            raw = reviewer_cfg.get(legacy_key)
        if raw is None:
            source = fallback
        elif isinstance(raw, list):
            source = raw
        else:
            source = [raw]
        values = [str(value).strip().lower() for value in source if str(value).strip()]
        return values or list(fallback)

    required_values = _extract_values("required_values", "requiredValues", DEFAULT_REVIEWER_REQUIRED)
    optional_values = _extract_values("optional_values", "optionalValues", DEFAULT_REVIEWER_OPTIONAL)
    allowed_values = {*required_values, *optional_values}
    if status not in allowed_values:
        choices = ", ".join(sorted(allowed_values))
        raise ValueError(f"status must be one of: {choices}")

    field_name = str(
        reviewer_cfg.get("tests_field")
        or reviewer_cfg.get("field")
        or DEFAULT_REVIEWER_FIELD
    )

    requested_by = args.requested_by or os.getenv("GIT_AUTHOR_NAME") or os.getenv("USER") or ""
    record: dict = {}
    if marker_path.exists():
        try:
            record = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            record = {}

    record.update(
        {
            "ticket": ticket,
            "slug": context.slug_hint or ticket,
            field_name: status,
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )
    if requested_by:
        record["requested_by"] = requested_by
    if args.note:
        record["note"] = args.note
    elif "note" in record and not record["note"]:
        record.pop("note", None)

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    state_label = "required" if status in required_values else status
    print(f"[claude-workflow] reviewer marker updated ({rel_marker} → {state_label}).")
    if status in required_values:
        print("[claude-workflow] format-and-test will trigger test tasks after the next write/edit.")


def _load_qa_tests_config(root: Path) -> tuple[list[list[str]], bool]:
    config_path = root / "config" / "gates.json"
    commands: list[list[str]] = []
    allow_skip = True
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return list(DEFAULT_QA_TEST_COMMAND), allow_skip

    qa_cfg = data.get("qa") or {}
    tests_cfg = qa_cfg.get("tests") or {}
    allow_skip = bool(tests_cfg.get("allow_skip", True))
    raw_commands = tests_cfg.get("commands", DEFAULT_QA_TEST_COMMAND)
    if isinstance(raw_commands, str):
        raw_commands = [raw_commands]
    if isinstance(raw_commands, list):
        for entry in raw_commands:
            parts: list[str] = []
            if isinstance(entry, list):
                parts = [str(item) for item in entry if str(item)]
            elif isinstance(entry, str):
                try:
                    parts = [token for token in shlex.split(entry) if token]
                except ValueError:
                    continue
            if parts:
                commands.append(parts)

    if not commands:
        commands = list(DEFAULT_QA_TEST_COMMAND)
    return commands, allow_skip


def _run_qa_tests(
    target: Path,
    *,
    ticket: str,
    slug_hint: str | None,
    branch: str | None,
    report_path: Path,
    allow_missing: bool,
) -> tuple[list[dict], str]:
    commands, allow_skip_cfg = _load_qa_tests_config(target)
    allow_skip = allow_missing or allow_skip_cfg

    tests_executed: list[dict] = []
    if not commands:
        summary = "skipped"
        return tests_executed, summary

    logs_dir = report_path.parent
    base_name = report_path.stem
    summary = "not-run"

    for index, cmd in enumerate(commands, start=1):
        log_path = logs_dir / f"{base_name}-tests{'' if len(commands) == 1 else f'-{index}'}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        status = "fail"
        exit_code: Optional[int] = None
        output = ""
        try:
            proc = subprocess.run(
                cmd,
                cwd=target,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            output = proc.stdout or ""
            exit_code = proc.returncode
            status = "pass" if proc.returncode == 0 else "fail"
        except FileNotFoundError as exc:
            status = "fail"
            output = f"command not found: {cmd[0]} ({exc})"
        log_path.write_text(output, encoding="utf-8")

        tests_executed.append(
            {
                "command": " ".join(cmd),
                "status": status,
                "log": _rel_path(log_path, target),
                "exit_code": exit_code,
            }
        )

    if any(entry.get("status") == "fail" for entry in tests_executed):
        summary = "fail"
    else:
        summary = "pass" if tests_executed else "not-run"

    if summary in {"not-run", "skipped"} and allow_skip:
        summary = "skipped"

    return tests_executed, summary


def _qa_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new.")

    branch = args.branch or _detect_branch(target)

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{branch}", branch or "")
        )

    report = args.report or "reports/qa/{ticket}.json"
    report = _fmt(report)

    allow_no_tests = bool(
        getattr(args, "allow_no_tests", False)
        or os.getenv("CLAUDE_QA_ALLOW_NO_TESTS", "").strip() == "1"
    )
    skip_tests = bool(getattr(args, "skip_tests", False) or os.getenv("CLAUDE_QA_SKIP_TESTS", "").strip() == "1")

    tests_executed: list[dict] = []
    tests_summary = "skipped" if skip_tests else "not-run"

    if not skip_tests:
        tests_executed, tests_summary = _run_qa_tests(
            target,
            ticket=ticket,
            slug_hint=slug_hint or None,
            branch=branch,
            report_path=target / report,
            allow_missing=allow_no_tests,
        )
        if tests_summary == "fail":
            print("[claude-workflow] QA tests failed; see reports/qa/*-tests.log.")
        elif tests_summary == "skipped":
            print("[claude-workflow] QA tests skipped (allow_no_tests enabled or no commands configured).")
        else:
            print("[claude-workflow] QA tests completed.")

    qa_args = ["--target", str(target)]
    if args.gate:
        qa_args.append("--gate")
    if args.dry_run:
        qa_args.append("--dry-run")
    if args.emit_json:
        qa_args.append("--emit-json")
    if args.format:
        qa_args.extend(["--format", args.format])
    if args.block_on:
        qa_args.extend(["--block-on", args.block_on])
    if args.warn_on:
        qa_args.extend(["--warn-on", args.warn_on])
    if args.scope:
        for scope in args.scope:
            qa_args.extend(["--scope", scope])

    qa_args.extend(["--ticket", ticket])
    if slug_hint and slug_hint != ticket:
        qa_args.extend(["--slug-hint", slug_hint])
    if branch:
        qa_args.extend(["--branch", branch])
    if report:
        qa_args.extend(["--report", report])

    _, allow_skip_cfg = _load_qa_tests_config(target)
    allow_no_tests_env = allow_no_tests or allow_skip_cfg

    old_env = {
        "QA_TESTS_SUMMARY": os.environ.get("QA_TESTS_SUMMARY"),
        "QA_TESTS_EXECUTED": os.environ.get("QA_TESTS_EXECUTED"),
        "QA_ALLOW_NO_TESTS": os.environ.get("QA_ALLOW_NO_TESTS"),
    }
    os.environ["QA_TESTS_SUMMARY"] = tests_summary
    os.environ["QA_TESTS_EXECUTED"] = json.dumps(tests_executed, ensure_ascii=False)
    os.environ["QA_ALLOW_NO_TESTS"] = "1" if allow_no_tests_env else "0"
    try:
        exit_code = _qa_agent.main(qa_args)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    if tests_summary == "fail":
        exit_code = max(exit_code, 1)
    elif tests_summary in {"not-run", "skipped"} and not allow_no_tests_env:
        exit_code = max(exit_code, 1)

    return exit_code


def _progress_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = context.resolved_ticket
    branch = args.branch or _detect_branch(target)
    config = _progress.ProgressConfig.load(target)
    result = _progress.check_progress(
        root=target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        source=args.source,
        branch=branch,
        config=config,
    )

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return result.exit_code()

    def _print_items(items: Sequence[str], prefix: str = "  - ", limit: int = 5) -> None:
        for index, item in enumerate(items):
            if index == limit:
                remaining = len(items) - limit
                print(f"{prefix}… (+{remaining})")
                break
            print(f"{prefix}{item}")

    if result.status.startswith("error:"):
        print(result.message or "BLOCK: проверка прогресса не пройдена.")
        if args.verbose and result.code_files:
            print("Изменённые файлы:")
            _print_items(result.code_files)
        return result.exit_code()

    if result.status.startswith("skip:"):
        print(result.message or "Прогресс-чек пропущен.")
        if args.verbose and result.code_files:
            print("Изменённые файлы:")
            _print_items(result.code_files)
        return 0

    label = _format_ticket_label(context)
    print(f"✅ Прогресс tasklist для `{label}` подтверждён.")
    if result.new_items:
        print("Новые чекбоксы:")
        _print_items(result.new_items)
    if args.verbose and result.code_files:
        print("Затронутые файлы:")
        _print_items(result.code_files)
    return 0

def _resolve_claude_dir(target: Path) -> Path:
    candidate = target / ".claude"
    if candidate.exists():
        return candidate
    if target.name == DEFAULT_PROJECT_SUBDIR:
        return target.parent / ".claude"
    return candidate

def _read_template_version(target: Path) -> str | None:
    version_file = _resolve_claude_dir(target) / ".template_version"
    if not version_file.exists():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None


def _write_template_version(target: Path) -> None:
    version_file = _resolve_claude_dir(target) / ".template_version"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"{VERSION}\n", encoding="utf-8")


def _resolve_feature_context(
    target: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> FeatureIdentifiers:
    return resolve_identifiers(target, ticket=ticket, slug_hint=slug_hint)


def _require_ticket(
    target: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> tuple[str, FeatureIdentifiers]:
    context = _resolve_feature_context(target, ticket=ticket, slug_hint=slug_hint)
    resolved = (context.resolved_ticket or "").strip()
    if not resolved:
        raise ValueError(
            "feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new."
        )
    return resolved, context


def _format_ticket_label(context: FeatureIdentifiers, fallback: str = "активной фичи") -> str:
    ticket = (context.resolved_ticket or "").strip() or fallback
    if context.slug_hint and context.slug_hint.strip() and context.slug_hint.strip() != ticket:
        return f"{ticket} (slug hint: {context.slug_hint.strip()})"
    return ticket


def _settings_path(target: Path) -> Path:
    return _resolve_claude_dir(target) / "settings.json"


def _load_settings_json(target: Path) -> dict:
    settings_file = _settings_path(target)
    if not settings_file.exists():
        raise FileNotFoundError(
            f"settings file not found at {settings_file}. Initialise the workflow or run from project root."
        )
    try:
        return json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cannot parse {settings_file}: {exc}") from exc


def _load_tests_settings(target: Path) -> dict:
    settings = _load_settings_json(target)
    automation = settings.get("automation") or {}
    tests_cfg = automation.get("tests")
    return tests_cfg if isinstance(tests_cfg, dict) else {}


def _reviewer_gate_config(target: Path) -> dict:
    tests_cfg = _load_tests_settings(target)
    reviewer_cfg = tests_cfg.get("reviewerGate") if isinstance(tests_cfg, dict) else None
    return reviewer_cfg if isinstance(reviewer_cfg, dict) else {}


def _reviewer_marker_path(target: Path, template: str, ticket: str, slug_hint: Optional[str]) -> Path:
    rel_text = template.replace("{ticket}", ticket)
    if "{slug}" in template:
        rel_text = rel_text.replace("{slug}", slug_hint or ticket)
    marker_path = Path(rel_text)
    if not marker_path.is_absolute():
        marker_path = (target / marker_path).resolve()
    else:
        marker_path = marker_path.resolve()
    target_root = target.resolve()
    if not _is_relative_to(marker_path, target_root):
        raise ValueError(
            f"reviewer marker path {marker_path} escapes project root {target_root}"
        )
    return marker_path


def _detect_branch(target: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=target,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    branch = proc.stdout.strip()
    if not branch or branch.upper() == "HEAD":
        return None
    return branch


_HANDOFF_SECTION_HINTS: Dict[str, Tuple[str, ...]] = {
    "qa": (
        "## 3. qa / проверки",
        "## qa",
        "## 3. qa",
        "## 3. qa / проверки",
    ),
    "review": (
        "## 2. реализация",
        "## реализация",
        "## implementation",
        "## 2. implementation",
    ),
    "research": (
        "## 1. аналитика и дизайн",
        "## аналитика",
        "## research",
        "## 7. примечания",
    ),
}


def _rel_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json_file(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {path}: {exc}") from exc


def _derive_tasks_from_findings(prefix: str, payload: Dict, report_label: str) -> List[str]:
    findings = payload.get("findings") or []
    tasks: List[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").strip().lower() or "info"
        scope = str(finding.get("scope") or "").strip()
        title = str(finding.get("title") or "").strip() or "issue"
        details = str(finding.get("recommendation") or finding.get("details") or "").strip()
        scope_label = f" ({scope})" if scope else ""
        details_part = f" — {details}" if details else ""
        tasks.append(f"- [ ] {prefix} [{severity}] {title}{scope_label}{details_part} (source: {report_label})")
    return tasks


def _derive_tasks_from_tests(payload: Dict, report_label: str) -> List[str]:
    tasks: List[str] = []
    summary = str(payload.get("tests_summary") or "").strip().lower() or "not-run"
    executed = payload.get("tests_executed") or []
    if summary in {"skipped", "not-run"}:
        tasks.append(f"- [ ] QA tests: запустить автотесты и приложить лог (source: {report_label})")
    for entry in executed:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status == "pass":
            continue
        command = str(entry.get("command") or "").strip() or "tests"
        log = str(entry.get("log") or entry.get("log_path") or "").strip()
        details = f" (лог: {log})" if log else ""
        status_label = status or "unknown"
        tasks.append(f"- [ ] QA tests: {status_label} → повторить `{command}`{details} (source: {report_label})")
    if summary == "fail" and not any(str(entry.get("status") or "").strip().lower() == "fail" for entry in executed):
        tasks.append(f"- [ ] QA tests: исправить упавшие тесты (source: {report_label})")
    return tasks


def _derive_tasks_from_research_context(payload: Dict, report_label: str, *, reuse_limit: int = 5) -> List[str]:
    tasks: List[str] = []
    profile = payload.get("profile") or {}
    recommendations = profile.get("recommendations") or []
    for rec in recommendations:
        rec_text = str(rec).strip()
        if not rec_text:
            continue
        tasks.append(f"- [ ] Research: {rec_text} (source: {report_label})")

    manual_notes = payload.get("manual_notes") or []
    for note in manual_notes:
        note_text = str(note).strip()
        if not note_text:
            continue
        tasks.append(f"- [ ] Research note: {note_text} (source: {report_label})")

    reuse_candidates = payload.get("reuse_candidates") or []
    for candidate in reuse_candidates[:reuse_limit]:
        if not isinstance(candidate, dict):
            continue
        path = str(candidate.get("path") or "").strip()
        if not path:
            continue
        score = candidate.get("score")
        has_tests = candidate.get("has_tests")
        extra_parts = []
        if score is not None:
            extra_parts.append(f"score={score}")
        if has_tests:
            extra_parts.append("tests")
        suffix = f" ({', '.join(extra_parts)})" if extra_parts else ""
        tasks.append(f"- [ ] Reuse candidate: {path}{suffix} (source: {report_label})")
    return tasks


def _dedupe_tasks(tasks: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for task in tasks:
        normalized = " ".join(task.strip().split())
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(task.strip())
    return deduped


def _extract_handoff_block(lines: List[str], source: str) -> tuple[int, int, List[str]]:
    start = -1
    end = -1
    marker = f"handoff:{source}"
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if marker in lowered and "start" in lowered:
            start = idx
            break
    if start != -1:
        for idx in range(start + 1, len(lines)):
            lowered = lines[idx].lower()
            if marker in lowered and "end" in lowered:
                end = idx
                break
    if start != -1 and end == -1:
        end = start
    existing: List[str] = []
    if start != -1 and end != -1:
        existing = [
            line
            for line in lines[start + 1 : end]
            if line.strip().startswith("- [ ]")
        ]
    return start, end, existing


def _find_section(lines: List[str], candidates: Sequence[str]) -> tuple[int, Optional[str]]:
    if not candidates:
        return len(lines), None
    lowered_candidates = [candidate.strip().lower() for candidate in candidates if candidate.strip()]
    heading_idx = None
    heading_label = None
    for idx, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("##"):
            for candidate in lowered_candidates:
                if stripped.startswith(candidate):
                    heading_idx = idx
                    heading_label = lines[idx].strip()
                    break
        if heading_idx is not None:
            break
    if heading_idx is None:
        return len(lines), None
    insert_idx = len(lines)
    for idx in range(heading_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("##"):
            insert_idx = idx
            break
    return insert_idx, heading_label


def _apply_handoff_tasks(
    text: str,
    *,
    source: str,
    report_label: str,
    tasks: Sequence[str],
    append: bool,
    section_candidates: Sequence[str],
) -> tuple[str, Optional[str], bool]:
    if not tasks:
        return text, None, False
    lines = text.splitlines()
    start, end, existing = _extract_handoff_block(lines, source)
    combined = list(existing) if append else []
    combined.extend(tasks)
    combined = _dedupe_tasks(combined)
    if not combined:
        return text, None, False

    if start != -1 and end != -1:
        del lines[start : end + 1]

    block_lines = [f"<!-- handoff:{source} start (source: {report_label}) -->"]
    block_lines.extend(combined)
    block_lines.append(f"<!-- handoff:{source} end -->")

    insert_idx, heading_label = _find_section(lines, section_candidates)
    prepend_blank = insert_idx > 0 and lines[insert_idx - 1].strip()
    if prepend_blank:
        block_lines.insert(0, "")
    append_blank = insert_idx < len(lines) and lines[insert_idx : insert_idx + 1] and lines[insert_idx].strip()
    if append_blank:
        block_lines.append("")
    new_lines = lines[:insert_idx] + block_lines + lines[insert_idx:]
    new_text = "\n".join(new_lines)
    if not new_text.endswith("\n"):
        new_text += "\n"
    changed = new_text != text
    return new_text, heading_label, changed


def _tasks_derive_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new.")

    source = (args.source or "").strip().lower()
    default_report = {
        "qa": "reports/qa/{ticket}.json",
        "review": "reports/review/{ticket}.json",
        "research": "reports/research/{ticket}-context.json",
    }.get(source)
    report_template = args.report or default_report
    if not report_template:
        raise ValueError("unsupported source; expected qa|review|research")

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
        )

    report_path = Path(_fmt(report_template))
    if not report_path.is_absolute():
        report_path = target / report_path
    report_label = _rel_path(report_path, target)
    if not report_path.exists():
        raise FileNotFoundError(f"{source} report not found at {report_label}")

    payload = _load_json_file(report_path)
    if source == "qa":
        derived_tasks = _derive_tasks_from_findings("QA", payload, report_label)
        derived_tasks.extend(_derive_tasks_from_tests(payload, report_label))
    elif source == "review":
        derived_tasks = _derive_tasks_from_findings("Review", payload, report_label)
    elif source == "research":
        derived_tasks = _derive_tasks_from_research_context(payload, report_label)
    else:
        derived_tasks = []

    derived_tasks = _dedupe_tasks(derived_tasks)
    if not derived_tasks:
        print(f"[claude-workflow] no tasks found in {source} report ({report_label}).")
        return 0

    tasklist_rel = Path("docs") / "tasklist" / f"{ticket}.md"
    tasklist_path = target / tasklist_rel
    if not tasklist_path.exists():
        raise FileNotFoundError(
            f"tasklist not found at {tasklist_rel}; create it via /tasks-new {ticket}."
        )
    tasklist_text = tasklist_path.read_text(encoding="utf-8")

    updated_text, heading_label, changed = _apply_handoff_tasks(
        tasklist_text,
        source=source,
        report_label=report_label,
        tasks=derived_tasks,
        append=bool(args.append),
        section_candidates=_HANDOFF_SECTION_HINTS.get(source, ()),
    )

    section_display = heading_label or "end of file"
    if args.dry_run:
        print(
            f"[claude-workflow] (dry-run) {len(derived_tasks)} task(s) "
            f"from {source} → {tasklist_rel} (section: {section_display})"
        )
        for task in derived_tasks:
            print(f"  {task}")
        return 0

    if not changed:
        print(f"[claude-workflow] tasklist already up to date for {source} report ({report_label}).")
        return 0

    tasklist_path.write_text(updated_text, encoding="utf-8")
    print(
        f"[claude-workflow] added {len(derived_tasks)} task(s) "
        f"from {source} report ({report_label}) to {tasklist_rel} "
        f"(section: {section_display}; mode={'append' if args.append else 'replace'})."
    )
    return 0


def _ensure_research_doc(
    target: Path,
    ticket: str,
    slug_hint: Optional[str],
    *,
    template_overrides: Optional[Dict[str, str]] = None,
) -> tuple[Optional[Path], bool]:
    template = target / "docs" / "research" / "template.md"
    destination = target / "docs" / "research" / f"{ticket}.md"
    if not template.exists():
        return None, False
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination, False
    content = template.read_text(encoding="utf-8")
    feature_label = slug_hint or ticket
    replacements = {
        "{{feature}}": feature_label,
        "{{ticket}}": ticket,
        "{{slug}}": slug_hint or "",
        "{{slug_hint}}": slug_hint or "",
        "{{date}}": dt.date.today().isoformat(),
        "{{owner}}": os.getenv("GIT_AUTHOR_NAME")
        or os.getenv("GIT_COMMITTER_NAME")
        or os.getenv("USER")
        or "",
    }
    if template_overrides:
        replacements.update(template_overrides)
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    destination.write_text(content, encoding="utf-8")
    return destination, True


def _iter_payload_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def _ensure_unique_backup(path: Path) -> Path:
    candidate = path.with_name(f"{path.name}.bak")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak{counter}")
        counter += 1
    return candidate


def _is_relative_to(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False

def _split_entries_by_root(
    entries: Iterable[tuple[Path, Path]],
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    workspace_entries: list[tuple[Path, Path]] = []
    project_entries: list[tuple[Path, Path]] = []
    for src, rel in entries:
        parts = rel.parts
        if parts and parts[0] in WORKSPACE_ROOT_DIRS:
            workspace_entries.append((src, rel))
        else:
            project_entries.append((src, rel))
    return workspace_entries, project_entries


def _split_manifest_entries(
    entries: Dict[str, Dict],
) -> tuple[Dict[str, Dict], Dict[str, Dict]]:
    workspace_entries: Dict[str, Dict] = {}
    project_entries: Dict[str, Dict] = {}
    for rel, entry in entries.items():
        parts = Path(rel).parts
        if parts and parts[0] in WORKSPACE_ROOT_DIRS:
            workspace_entries[rel] = entry
        else:
            project_entries[rel] = entry
    return workspace_entries, project_entries


def _select_payload_entries(
    payload_path: Path,
    includes: Iterable[Path] | None = None,
    *,
    strip_prefix: str | None = None,
) -> list[tuple[Path, Path]]:
    include_list = list(includes or [])
    include_rel: list[Path] = []
    if strip_prefix and include_list:
        prefix_path = Path(strip_prefix.strip("/"))
        include_rel = []
        for inc in include_list:
            if inc.parts and inc.parts[0] == prefix_path.name:
                include_rel.append(inc)
            else:
                include_rel.append(prefix_path / inc)
    else:
        include_rel = include_list
    entries: list[tuple[Path, Path]] = []
    normalized_prefix = ""
    if strip_prefix:
        normalized_prefix = strip_prefix.rstrip("/").lstrip("/") + "/"
    for src in _iter_payload_files(payload_path):
        rel = src.relative_to(payload_path)
        rel_posix = rel.as_posix()
        if include_rel and not any(_is_relative_to(rel, inc) for inc in include_rel):
            continue
        if normalized_prefix:
            if not rel_posix.startswith(normalized_prefix):
                continue
            stripped_rel = Path(rel_posix[len(normalized_prefix) :].lstrip("/"))
        else:
            if rel.parts and rel.parts[0] == DEFAULT_PROJECT_SUBDIR:
                stripped_rel = Path(*rel.parts[1:])
            else:
                stripped_rel = rel
        entries.append((src, stripped_rel))
    return entries


def _copy_payload_entries(
    destination_root: Path,
    entries: Iterable[tuple[Path, Path]],
    *,
    force: bool,
    dry_run: bool,
    create_backups: bool,
) -> tuple[list[str], list[str], list[str]]:
    updated: list[str] = []
    skipped: list[str] = []
    backups: list[str] = []

    for src, rel in entries:
        dest = destination_root / rel

        if not dest.exists():
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            updated.append(str(rel))
            continue

        try:
            identical = filecmp.cmp(src, dest, shallow=False)
        except OSError:
            identical = False

        if identical:
            if not dry_run:
                shutil.copy2(src, dest)
            updated.append(str(rel))
            continue

        if force:
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                backup_path: Path | None = None
                if create_backups:
                    backup_path = _ensure_unique_backup(dest)
                    shutil.copy2(dest, backup_path)
                    try:
                        backups.append(str(backup_path.relative_to(destination_root)))
                    except ValueError:
                        backups.append(backup_path.as_posix())
                shutil.copy2(src, dest)
            updated.append(str(rel))
        else:
            skipped.append(str(rel))

    return updated, skipped, backups


def _detect_manifest_prefix(manifest: Dict[str, Dict]) -> str | None:
    prefix = f"{DEFAULT_PROJECT_SUBDIR}/"
    keys = list(manifest.keys())
    if keys and all(key.startswith(prefix) for key in keys):
        return prefix
    return None


def _strip_manifest_prefix(manifest: Dict[str, Dict], prefix: str) -> Dict[str, Dict]:
    normalized = prefix.rstrip("/") + "/"
    stripped: Dict[str, Dict] = {}
    for rel, entry in manifest.items():
        if not rel.startswith(normalized):
            return manifest
        new_rel = rel[len(normalized) :]
        updated_entry = dict(entry)
        updated_entry["path"] = new_rel
        stripped[new_rel] = updated_entry
    return stripped


def _normalise_include(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"include path must be relative: {value}")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"include path cannot contain '..': {value}")
    return path


def _upgrade_command(args: argparse.Namespace) -> None:
    workspace_root, project_root = _require_workflow_root(Path(args.target).resolve())

    current_version = _read_template_version(project_root)
    if current_version and current_version == VERSION:
        print(
            f"[claude-workflow] project already on template version {VERSION};"
            " upgrade will refresh files if templates changed."
        )

    with _payload_root(args.release, args.cache_dir) as payload_path:
        manifest = _load_manifest(payload_path)
        manifest_prefix = _detect_manifest_prefix(manifest)
        manifest_view = _strip_manifest_prefix(manifest, manifest_prefix) if manifest_prefix else manifest
        entries = _select_payload_entries(payload_path, strip_prefix=manifest_prefix)
        managed_manifest, _ = _filter_manifest_for_entries(entries, manifest_view)
        workspace_entries, project_entries = _split_entries_by_root(entries)
        workspace_manifest, project_manifest = _split_manifest_entries(managed_manifest)
        _report_manifest_diff(project_root, project_manifest, prefix="upgrade")
        if workspace_manifest:
            _report_manifest_diff(workspace_root, workspace_manifest, prefix="upgrade:workspace")
        updated, skipped, backups = _copy_payload_entries(
            project_root,
            project_entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )
        ws_updated, ws_skipped, ws_backups = _copy_payload_entries(
            workspace_root,
            workspace_entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )
        updated.extend(ws_updated)
        skipped.extend(ws_skipped)
        backups.extend(ws_backups)

    if args.dry_run:
        print(
            f"[claude-workflow] upgrade dry-run: {len(updated)} files would update,"
            f" {len(skipped)} would be skipped."
        )
        if skipped:
            print("[claude-workflow] skipped (differs locally):")
            for item in skipped:
                print(f"  - {item}")
        return

    _write_template_version(project_root)

    report_lines = [
        f"claude-workflow upgrade ({VERSION})",
        f"updated: {len(updated)}",
        f"skipped (manual merge required): {len(skipped)}",
        f"backups created: {len(backups)}",
        "",
    ]

    if skipped:
        report_lines.append("Skipped files:")
        report_lines.extend(f"  - {item}" for item in skipped)
        report_lines.append("")

    if backups:
        report_lines.append("Backups:")
        report_lines.extend(f"  - {item}" for item in backups)
        report_lines.append("")

    report_path = _resolve_claude_dir(project_root) / "upgrade-report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(
        f"[claude-workflow] upgrade complete: {len(updated)} files updated,"
        f" {len(skipped)} skipped. Report saved to {report_path}."
    )
    if skipped:
        print("[claude-workflow] Some files differ locally; review report for details.")


def _sync_command(args: argparse.Namespace) -> None:
    target_path = Path(args.target).resolve()
    workspace_root, project_root = resolve_project_root(target_path, DEFAULT_PROJECT_SUBDIR)
    if project_root.exists():
        pass
    elif not args.dry_run:
        project_root.mkdir(parents=True, exist_ok=True)
    # for dry-run we don't create project_root; proceed with computed path

    raw_includes = args.include or [".claude"]
    try:
        includes = [_normalise_include(item) for item in raw_includes]
    except ValueError as exc:
        raise ValueError(f"invalid include path: {exc}") from exc

    with _payload_root(args.release, args.cache_dir) as payload_path:
        manifest = _load_manifest(payload_path)
        manifest_prefix = _detect_manifest_prefix(manifest)
        adjusted_includes: list[Path] = []
        for include in includes:
            candidate = payload_path / include
            if not candidate.exists() and manifest_prefix:
                prefixed = Path(manifest_prefix) / include
                if (payload_path / prefixed).exists():
                    include = prefixed
                    candidate = payload_path / prefixed
            if not candidate.exists():
                fallback = Path(DEFAULT_PROJECT_SUBDIR) / include
                if (payload_path / fallback).exists():
                    include = fallback
                    candidate = payload_path / fallback
            if not candidate.exists():
                raise FileNotFoundError(f"payload path not found: {include}")
            adjusted_includes.append(include)
        manifest_view = _strip_manifest_prefix(manifest, manifest_prefix) if manifest_prefix else manifest
        if not manifest_prefix:
            prefix = f"{DEFAULT_PROJECT_SUBDIR}/"
            extras: Dict[str, Dict] = {}
            for rel, entry in manifest.items():
                if rel.startswith(prefix):
                    extras[rel[len(prefix) :]] = entry
            if extras:
                manifest_view = {**manifest, **extras}
        entries = _select_payload_entries(payload_path, adjusted_includes, strip_prefix=manifest_prefix)
        managed_manifest, _ = _filter_manifest_for_entries(entries, manifest_view)
        workspace_entries, project_entries = _split_entries_by_root(entries)
        workspace_manifest, project_manifest = _split_manifest_entries(managed_manifest)
        prefix = f"sync:{','.join(item.as_posix() for item in includes)}"
        _report_manifest_diff(project_root, project_manifest, prefix=prefix)
        if workspace_manifest:
            _report_manifest_diff(workspace_root, workspace_manifest, prefix=f"{prefix}:workspace")
        updated, skipped, backups = _copy_payload_entries(
            project_root,
            project_entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )
        ws_updated, ws_skipped, ws_backups = _copy_payload_entries(
            workspace_root,
            workspace_entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )
        updated.extend(ws_updated)
        skipped.extend(ws_skipped)
        backups.extend(ws_backups)

    if args.dry_run:
        print(
            f"[claude-workflow] sync dry-run: {len(updated)} files would update,"
            f" {len(skipped)} would be skipped."
        )
        if skipped:
            print("[claude-workflow] skipped (differs locally):")
            for item in skipped:
                print(f"  - {item}")
        return

    if any(_is_relative_to(include, Path(".claude")) for include in includes):
        _write_template_version(project_root)

    print(
        f"[claude-workflow] sync complete: {len(updated)} files updated,"
        f" {len(skipped)} skipped."
    )
    if skipped:
        print("[claude-workflow] Skipped files (manual merge required):")
        for item in skipped:
            print(f"  - {item}")
    if backups:
        print("[claude-workflow] Backups:")
        for item in backups:
            print(f"  - {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-workflow",
        description="Bootstrap and manage the Claude Code workflow.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Generate workflow scaffolding in the target directory."
    )
    init_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root for the workflow (default: current; workflow always lives in ./aidd).",
    )
    init_parser.add_argument(
        "--commit-mode",
        choices=("ticket-prefix", "conventional", "mixed"),
        default="ticket-prefix",
        help="Commit message policy enforced in config/conventions.json.",
    )
    init_parser.add_argument(
        "--enable-ci",
        action="store_true",
        help="Add GitHub Actions workflow (manual trigger).",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without modifying files.",
    )
    init_parser.set_defaults(func=_init_command)

    smoke_parser = subparsers.add_parser(
        "smoke", help="Run the bundled smoke test to validate the workflow bootstrap."
    )
    smoke_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit verbose logs when running the smoke scenario.",
    )
    smoke_parser.set_defaults(func=_smoke_command)

    set_active_feature_parser = subparsers.add_parser(
        "set-active-feature",
        help="Persist the active feature ticket and refresh Researcher targets.",
    )
    set_active_feature_parser.add_argument("ticket", help="Feature ticket identifier to persist.")
    set_active_feature_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    set_active_feature_parser.add_argument(
        "--paths",
        help="Optional colon-separated list of extra paths for Researcher scope.",
    )
    set_active_feature_parser.add_argument(
        "--keywords",
        help="Optional comma-separated keywords to seed Researcher search.",
    )
    set_active_feature_parser.add_argument(
        "--config",
        help="Path to conventions JSON with researcher section (defaults to config/conventions.json).",
    )
    set_active_feature_parser.add_argument(
        "--slug-note",
        dest="slug_note",
        help="Optional slug hint to persist alongside the ticket.",
    )
    set_active_feature_parser.add_argument(
        "--skip-prd-scaffold",
        action="store_true",
        help="Skip automatic docs/prd/<ticket>.prd.md scaffold creation.",
    )
    set_active_feature_parser.set_defaults(func=_set_active_feature_command)

    set_active_stage_parser = subparsers.add_parser(
        "set-active-stage",
        help="Persist the active workflow stage in docs/.active_stage.",
    )
    set_active_stage_parser.add_argument(
        "stage",
        help=(
            "Stage name (idea/research/plan/review-plan/review-prd/"
            "tasklist/implement/review/qa)."
        ),
    )
    set_active_stage_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    set_active_stage_parser.add_argument(
        "--allow-custom",
        action="store_true",
        help="Allow arbitrary stage values (skip validation).",
    )
    set_active_stage_parser.set_defaults(func=_set_active_stage_command)

    migrate_ticket_parser = subparsers.add_parser(
        "migrate-ticket",
        help="Upgrade workflow artefacts to the ticket-first format.",
    )
    migrate_ticket_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    migrate_ticket_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without modifying files.",
    )
    migrate_ticket_parser.set_defaults(func=_migrate_ticket_command)

    migrate_tasklist_parser = subparsers.add_parser(
        "migrate-tasklist",
        help="Move legacy tasklist.md into docs/tasklist/<slug>.md (pre-ticket).",
    )
    migrate_tasklist_parser.add_argument(
        "--slug",
        help="Feature slug to use; defaults to docs/.active_feature or single plan file.",
    )
    migrate_tasklist_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    migrate_tasklist_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing docs/tasklist/<slug>.md if present.",
    )
    migrate_tasklist_parser.set_defaults(func=_migrate_tasklist_command)

    prd_review_parser = subparsers.add_parser(
        "prd-review",
        help="Run lightweight PRD review heuristics and emit reports/prd/<ticket>.json.",
    )
    prd_review_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    prd_review_parser.add_argument(
        "--ticket",
        help="Feature ticket to analyse (defaults to docs/.active_ticket).",
    )
    prd_review_parser.add_argument(
        "--slug",
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature when available).",
    )
    prd_review_parser.add_argument(
        "--prd",
        type=Path,
        help="Explicit path to PRD file. Defaults to docs/prd/<ticket>.prd.md.",
    )
    prd_review_parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to store JSON report. Directories are created automatically.",
    )
    prd_review_parser.add_argument(
        "--emit-text",
        action="store_true",
        help="Print a human-readable summary in addition to JSON output.",
    )
    prd_review_parser.add_argument(
        "--stdout-format",
        choices=("json", "text", "auto"),
        default="auto",
        help="Format for stdout output (default: auto). Auto prints text when --emit-text is used.",
    )
    prd_review_parser.set_defaults(func=_prd_review_command)

    plan_review_gate_parser = subparsers.add_parser(
        "plan-review-gate",
        help="Validate plan review readiness (used by hooks).",
    )
    plan_review_gate_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    plan_review_gate_parser.add_argument("--ticket", required=True, help="Active feature ticket.")
    plan_review_gate_parser.add_argument("--file-path", default="", help="Path being modified.")
    plan_review_gate_parser.add_argument("--branch", default="", help="Current branch name.")
    plan_review_gate_parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    plan_review_gate_parser.add_argument(
        "--skip-on-plan-edit",
        action="store_true",
        help="Return success when the plan file itself is being edited.",
    )
    plan_review_gate_parser.set_defaults(func=_plan_review_gate_command)

    prd_review_gate_parser = subparsers.add_parser(
        "prd-review-gate",
        help="Validate PRD review readiness (used by hooks).",
    )
    prd_review_gate_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    prd_review_gate_parser.add_argument(
        "--ticket",
        "--slug",
        dest="ticket",
        required=True,
        help="Active feature ticket (legacy alias: --slug).",
    )
    prd_review_gate_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        default="",
        help="Optional slug hint used for messaging (defaults to docs/.active_feature).",
    )
    prd_review_gate_parser.add_argument(
        "--file-path",
        default="",
        help="Path being modified (used to skip checks for direct PRD edits).",
    )
    prd_review_gate_parser.add_argument(
        "--branch",
        default="",
        help="Current branch name for branch-based filters.",
    )
    prd_review_gate_parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    prd_review_gate_parser.add_argument(
        "--skip-on-prd-edit",
        action="store_true",
        help="Return success when the PRD file itself is being edited.",
    )
    prd_review_gate_parser.set_defaults(func=_prd_review_gate_command)

    researcher_context_parser = subparsers.add_parser(
        "researcher-context",
        help="Run researcher context builder (pass through to module CLI).",
    )
    researcher_context_parser.add_argument(
        "forward_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the researcher context tool.",
    )
    researcher_context_parser.set_defaults(func=_researcher_context_command)

    context_gc_parser = subparsers.add_parser(
        "context-gc",
        help="Run context GC hooks (precompact/sessionstart/pretooluse/userprompt).",
    )
    context_gc_parser.add_argument(
        "mode",
        choices=("precompact", "sessionstart", "pretooluse", "userprompt"),
        help="Context GC mode to execute.",
    )
    context_gc_parser.set_defaults(func=_context_gc_command)

    analyst_parser = subparsers.add_parser(
        "analyst-check",
        help="Validate the analyst dialog (Вопрос/Ответ) for the active feature PRD.",
    )
    analyst_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to validate (defaults to docs/.active_ticket).",
    )
    analyst_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for messaging (defaults to docs/.active_feature if present).",
    )
    analyst_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    analyst_parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate config.gates analyst branch rules.",
    )
    analyst_parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Allow Status: BLOCKED without failing validation.",
    )
    analyst_parser.add_argument(
        "--no-ready-required",
        action="store_true",
        help="Skip enforcing Status: READY (useful mid-dialog).",
    )
    analyst_parser.add_argument(
        "--min-questions",
        type=int,
        help="Override minimum number of questions expected from analyst.",
    )
    analyst_parser.set_defaults(func=_analyst_check_command)

    research_check_parser = subparsers.add_parser(
        "research-check",
        help="Validate the Researcher report (docs/research + reports/research).",
    )
    research_check_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to validate (defaults to docs/.active_ticket).",
    )
    research_check_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for messaging (defaults to docs/.active_feature if present).",
    )
    research_check_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    research_check_parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate config.gates researcher branch rules.",
    )
    research_check_parser.set_defaults(func=_research_check_command)

    research_parser = subparsers.add_parser(
        "research",
        help="Collect scope and context for the Researcher agent.",
    )
    research_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active_ticket).",
    )
    research_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for templates and keywords (defaults to docs/.active_feature).",
    )
    research_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    research_parser.add_argument(
        "--config",
        help="Path to conventions JSON containing the researcher section (defaults to config/conventions.json).",
    )
    research_parser.add_argument(
        "--paths",
        help="Colon-separated list of additional paths to scan (overrides defaults from conventions).",
    )
    research_parser.add_argument(
        "--paths-relative",
        choices=("workspace", "aidd"),
        help="Treat relative paths as workspace-rooted (default) or under aidd/. When omitted, defaults to workspace if target is aidd.",
    )
    research_parser.add_argument(
        "--keywords",
        help="Comma-separated list of extra keywords to search for.",
    )
    research_parser.add_argument(
        "--note",
        dest="notes",
        action="append",
        help="Free-form note or @path to include in the context; use '-' to read stdin once.",
    )
    research_parser.add_argument(
        "--limit",
        type=int,
        default=24,
        help="Maximum number of code/document matches to capture (default: 24).",
    )
    research_parser.add_argument(
        "--output",
        help="Override output JSON path (default: reports/research/<ticket>-context.json).",
    )
    research_parser.add_argument(
        "--targets-only",
        action="store_true",
        help="Only refresh targets JSON; skip content scan and context export.",
    )
    research_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print context JSON to stdout without writing files (targets are still refreshed).",
    )
    research_parser.add_argument(
        "--deep-code",
        action="store_true",
        help="Collect code symbols/imports/tests for reuse candidates (without building call graph).",
    )
    research_parser.add_argument(
        "--reuse-only",
        action="store_true",
        help="Skip keyword matches and focus on reuse candidates in the output.",
    )
    research_parser.add_argument(
        "--langs",
        help="Comma-separated list of languages to scan for deep analysis (py,kt,kts,java).",
    )
    research_parser.add_argument(
        "--call-graph",
        action="store_true",
        help="Build call/import graph (supported languages via tree-sitter if available).",
    )
    research_parser.add_argument(
        "--graph-engine",
        choices=["auto", "none", "ts"],
        default="auto",
        help="Engine for call graph: auto (tree-sitter when available), none (disable), ts (force tree-sitter).",
    )
    research_parser.add_argument(
        "--graph-langs",
        help="Comma-separated list of languages for call graph (kt,kts,java; others ignored).",
    )
    research_parser.add_argument(
        "--graph-filter",
        help="Regex to keep only matching call graph edges (matches file/caller/callee). Defaults to ticket/keywords.",
    )
    research_parser.add_argument(
        "--graph-limit",
        type=int,
        default=_DEFAULT_GRAPH_LIMIT,
        help=f"Maximum number of call graph edges to keep in focused graph (default: {_DEFAULT_GRAPH_LIMIT}).",
    )
    research_parser.add_argument(
        "--no-template",
        action="store_true",
        help="Do not materialise docs/research/<ticket>.md from the template.",
    )
    research_parser.add_argument(
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /idea-new integrations (warn on empty matches).",
    )
    research_parser.set_defaults(func=_research_command)

    reviewer_tests_parser = subparsers.add_parser(
        "reviewer-tests",
        help="Update reviewer test requirement marker for the active feature.",
    )
    reviewer_tests_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    reviewer_tests_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for marker metadata.",
    )
    reviewer_tests_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    reviewer_tests_parser.add_argument(
        "--status",
        default="required",
        help="Tests state to store in the marker (default: required).",
    )
    reviewer_tests_parser.add_argument(
        "--note",
        help="Optional note stored alongside the reviewer marker.",
    )
    reviewer_tests_parser.add_argument(
        "--requested-by",
        help="Override requested_by field in the marker (defaults to $USER).",
    )
    reviewer_tests_parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove the marker instead of updating it.",
    )
    reviewer_tests_parser.set_defaults(func=_reviewer_tests_command)

    tasks_parser = subparsers.add_parser(
        "tasks-derive",
        help="Generate tasklist candidates from QA/Review/Research reports.",
    )
    tasks_parser.add_argument(
        "--source",
        choices=("qa", "review", "research"),
        required=True,
        help="Report source to derive tasks from.",
    )
    tasks_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    tasks_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    tasks_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    tasks_parser.add_argument(
        "--report",
        help="Optional report path override (default depends on --source).",
    )
    tasks_parser.add_argument(
        "--append",
        action="store_true",
        help="Preserve existing handoff block and append new items instead of replacing it.",
    )
    tasks_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without modifying files.",
    )
    tasks_parser.set_defaults(func=_tasks_derive_command)

    qa_parser = subparsers.add_parser(
        "qa",
        help="Run QA agent and generate reports/qa/<ticket>.json.",
    )
    qa_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    qa_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    qa_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    qa_parser.add_argument(
        "--branch",
        help="Git branch name for logging (autodetected by default).",
    )
    qa_parser.add_argument(
        "--report",
        help="Path to JSON report (default: reports/qa/<ticket>.json).",
    )
    qa_parser.add_argument(
        "--block-on",
        help="Comma-separated severities treated as blockers (pass-through to qa-agent).",
    )
    qa_parser.add_argument(
        "--warn-on",
        help="Comma-separated severities treated as warnings (pass-through to qa-agent).",
    )
    qa_parser.add_argument(
        "--scope",
        action="append",
        help="Optional scope filters (pass-through to qa-agent).",
    )
    qa_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="qa-agent output format (default: json).",
    )
    qa_parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Emit JSON to stdout even in gate mode.",
    )
    qa_parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip QA test run (not recommended; override is respected in gate mode).",
    )
    qa_parser.add_argument(
        "--allow-no-tests",
        action="store_true",
        help="Allow QA to proceed without tests (or with skipped test commands).",
    )
    qa_parser.add_argument(
        "--gate",
        action="store_true",
        help="Gate mode: non-zero exit code on blocker severities.",
    )
    qa_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gate mode without failing on blockers.",
    )
    qa_parser.set_defaults(func=_qa_command)

    progress_parser = subparsers.add_parser(
        "progress",
        help="Check that docs/tasklist/<ticket>.md has new completed items after code changes.",
    )
    progress_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to check (defaults to docs/.active_ticket).",
    )
    progress_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    progress_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    progress_parser.add_argument(
        "--branch",
        help="Git branch name used to evaluate skip_branches (autodetected by default).",
    )
    progress_parser.add_argument(
        "--source",
        choices=("manual", "implement", "qa", "review", "gate", "handoff"),
        default="manual",
        help="Context in which the check is executed (default: manual).",
    )
    progress_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit result as JSON for scripting.",
    )
    progress_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed lists of code changes and checkbox updates.",
    )
    progress_parser.set_defaults(func=_progress_command)

    upgrade_parser = subparsers.add_parser(
        "upgrade", help="Refresh workflow files from the latest template."
    )
    upgrade_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    upgrade_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files even if they differ; backups are created first.",
    )
    upgrade_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing files.",
    )
    upgrade_parser.add_argument(
        "--release",
        help=(
            "Download payload from GitHub Releases instead of bundled templates. "
            "Accepts TAG or owner/repo@TAG. Use 'latest' for the newest release."
        ),
    )
    upgrade_parser.add_argument(
        "--cache-dir",
        help=(
            "Override directory used to cache downloaded payloads "
            "(defaults to $CLAUDE_WORKFLOW_CACHE or ~/.cache/claude-workflow)."
        ),
    )
    upgrade_parser.set_defaults(func=_upgrade_command)

    sync_parser = subparsers.add_parser(
        "sync",
        help="Synchronise payload fragments (defaults to .claude) into the target directory.",
    )
    sync_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    sync_parser.add_argument(
        "--include",
        action="append",
        help=(
            "Relative payload path to sync. Can be specified multiple times; "
            "defaults to .claude if omitted."
        ),
    )
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files even if they differ; backups are created first.",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing files.",
    )
    sync_parser.add_argument(
        "--release",
        help=(
            "Download payload from GitHub Releases instead of bundled templates. "
            "Accepts TAG or owner/repo@TAG. Use 'latest' for the newest release."
        ),
    )
    sync_parser.add_argument(
        "--cache-dir",
        help=(
            "Override directory used to cache downloaded payloads "
            "(defaults to $CLAUDE_WORKFLOW_CACHE or ~/.cache/claude-workflow)."
        ),
    )
    sync_parser.set_defaults(func=_sync_command)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except subprocess.CalledProcessError as exc:
        # Propagate the same exit code but provide human-friendly output.
        parser.exit(exc.returncode, f"[claude-workflow] command failed: {exc}\n")
    except Exception as exc:  # pragma: no cover - safety net
        parser.exit(1, f"[claude-workflow] {exc}\n")
    if isinstance(result, int):
        return result
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
