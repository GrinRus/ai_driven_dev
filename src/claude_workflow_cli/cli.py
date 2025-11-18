from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import hashlib
import json
import os
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
    resolve_identifiers,
    write_identifiers,
)

from claude_workflow_cli import progress as _progress
from claude_workflow_cli.tools.analyst_guard import (
    AnalystValidationError,
    load_settings as _load_analyst_settings,
    validate_prd as _validate_analyst_prd,
)
from claude_workflow_cli.tools.researcher_context import (
    ResearcherContextBuilder,
    _parse_keywords as _research_parse_keywords,
    _parse_notes as _research_parse_notes,
    _parse_paths as _research_parse_paths,
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
    target: Path, manifest_entries: Dict[str, Dict], *, prefix: str
) -> Tuple[List[str], List[str]]:
    new_files: List[str] = []
    changed_files: List[str] = []
    for rel, entry in manifest_entries.items():
        destination = target / rel
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
    payload (shell scripts, templates, presets, etc.).  The context manager
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
    target.mkdir(parents=True, exist_ok=True)

    current_version = _read_template_version(target)
    if current_version and current_version != VERSION:
        print(
            f"[claude-workflow] existing template version {current_version} detected;"
            f" CLI {VERSION} will refresh files."
        )

    with _payload_root() as payload_path:
        script = payload_path / "init-claude-workflow.sh"
        if not script.exists():
            raise FileNotFoundError(f"bootstrap script not found at {script}")
        env = {"CLAUDE_TEMPLATE_DIR": str(payload_path)}
        cmd = ["bash", str(script), *extra_args]
        _run_subprocess(cmd, cwd=target, env=env)
    _write_template_version(target)


def _run_smoke(verbose: bool) -> None:
    with _payload_root() as payload_path:
        script = payload_path / "scripts" / "smoke-workflow.sh"
        if not script.exists():
            raise FileNotFoundError(f"smoke script not found at {script}")
        cmd = ["bash", str(script)]
        env = {}
        if verbose:
            env["SMOKE_VERBOSE"] = "1"
        # smoke script handles its own temp directory; run from payload root
        _run_subprocess(cmd, cwd=payload_path, env=env)


def _init_command(args: argparse.Namespace) -> None:
    script_args = ["--commit-mode", args.commit_mode]
    if args.enable_ci:
        script_args.append("--enable-ci")
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    if getattr(args, "prompt_locale", None):
        script_args.extend(["--prompt-locale", args.prompt_locale])
    _run_init(Path(args.target).resolve(), script_args)


def _preset_command(args: argparse.Namespace) -> None:
    script_args: List[str] = ["--preset", args.name]
    if getattr(args, "ticket", None):
        script_args.extend(["--ticket", args.ticket])
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    if getattr(args, "prompt_locale", None):
        script_args.extend(["--prompt-locale", args.prompt_locale])
    _run_init(Path(args.target).resolve(), script_args)


def _smoke_command(args: argparse.Namespace) -> None:
    _run_smoke(args.verbose)


def _analyst_check_command(args: argparse.Namespace) -> None:
    target = Path(args.target).resolve()
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


def _research_command(args: argparse.Namespace) -> None:
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

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
    builder = ResearcherContextBuilder(target, config_path=config_path)
    scope = builder.build_scope(ticket, slug_hint=feature_context.slug_hint)
    scope = builder.extend_scope(
        scope,
        extra_paths=_research_parse_paths(args.paths),
        extra_keywords=_research_parse_keywords(args.keywords),
        extra_notes=_research_parse_notes(getattr(args, "notes", None), target),
    )

    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(target).as_posix()
    print(
        f"[claude-workflow] researcher targets saved to {rel_targets} "
        f"({len(scope.paths)} paths, {len(scope.docs)} docs)."
    )

    if args.targets_only:
        return

    collected_context = builder.collect_context(scope, limit=args.limit)
    collected_context["auto_mode"] = bool(getattr(args, "auto", False))
    match_count = len(collected_context["matches"])
    if match_count == 0:
        print(
            f"[claude-workflow] researcher found 0 matches for `{ticket}` — зафиксируйте baseline и статус pending в docs/research/{ticket}.md."
        )
    if args.dry_run:
        print(json.dumps(collected_context, indent=2, ensure_ascii=False))
        return

    output = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, collected_context, output=output)
    rel_output = output_path.relative_to(target).as_posix()
    print(
        f"[claude-workflow] researcher context saved to {rel_output} "
        f"({match_count} matches)."
    )

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
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

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


def _progress_command(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

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

def _read_template_version(target: Path) -> str | None:
    version_file = target / ".claude" / ".template_version"
    if not version_file.exists():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None


def _write_template_version(target: Path) -> None:
    version_file = target / ".claude" / ".template_version"
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
    return target / ".claude" / "settings.json"


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


def _ensure_research_doc(
    target: Path,
    ticket: str,
    slug_hint: Optional[str],
    *,
    template_overrides: Optional[Dict[str, str]] = None,
) -> tuple[Optional[Path], bool]:
    template = target / "docs" / "templates" / "research-summary.md"
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


def _select_payload_entries(
    payload_path: Path, includes: Iterable[Path] | None = None
) -> list[tuple[Path, Path]]:
    include_list = list(includes or [])
    entries: list[tuple[Path, Path]] = []
    for src in _iter_payload_files(payload_path):
        rel = src.relative_to(payload_path)
        if include_list and not any(_is_relative_to(rel, inc) for inc in include_list):
            continue
        entries.append((src, rel))
    return entries


def _copy_payload_entries(
    target: Path,
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
        dest = target / rel

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
                    backups.append(str(backup_path.relative_to(target)))
                shutil.copy2(src, dest)
            updated.append(str(rel))
        else:
            skipped.append(str(rel))

    return updated, skipped, backups


def _normalise_include(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"include path must be relative: {value}")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"include path cannot contain '..': {value}")
    return path


def _upgrade_command(args: argparse.Namespace) -> None:
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

    current_version = _read_template_version(target)
    if current_version and current_version == VERSION:
        print(
            f"[claude-workflow] project already on template version {VERSION};"
            " upgrade will refresh files if templates changed."
        )

    with _payload_root(args.release, args.cache_dir) as payload_path:
        manifest = _load_manifest(payload_path)
        entries = _select_payload_entries(payload_path)
        managed_manifest, _ = _filter_manifest_for_entries(entries, manifest)
        _report_manifest_diff(target, managed_manifest, prefix="upgrade")
        updated, skipped, backups = _copy_payload_entries(
            target,
            entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )

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

    _write_template_version(target)

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

    report_path = target / ".claude" / "upgrade-report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(
        f"[claude-workflow] upgrade complete: {len(updated)} files updated,"
        f" {len(skipped)} skipped. Report saved to {report_path}."
    )
    if skipped:
        print("[claude-workflow] Some files differ locally; review report for details.")


def _sync_command(args: argparse.Namespace) -> None:
    target = Path(args.target).resolve()
    if not target.exists():
        raise FileNotFoundError(f"target directory {target} does not exist")

    raw_includes = args.include or [".claude"]
    try:
        includes = [_normalise_include(item) for item in raw_includes]
    except ValueError as exc:
        raise ValueError(f"invalid include path: {exc}") from exc

    with _payload_root(args.release, args.cache_dir) as payload_path:
        for include in includes:
            if not (payload_path / include).exists():
                raise FileNotFoundError(f"payload path not found: {include}")
        entries = _select_payload_entries(payload_path, includes)
        manifest = _load_manifest(payload_path)
        managed_manifest, _ = _filter_manifest_for_entries(entries, manifest)
        prefix = f"sync:{','.join(item.as_posix() for item in includes)}"
        _report_manifest_diff(target, managed_manifest, prefix=prefix)
        updated, skipped, backups = _copy_payload_entries(
            target,
            entries,
            force=args.force,
            dry_run=args.dry_run,
            create_backups=True,
        )

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
        _write_template_version(target)

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
        description="Bootstrap and manage the Claude Code workflow presets.",
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
        help="Directory where the workflow should be initialised (default: current)",
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
    init_parser.add_argument(
        "--prompt-locale",
        choices=("ru", "en"),
        default="ru",
        help="Copy prompts in the specified locale into .claude/ (default: ru).",
    )
    init_parser.set_defaults(func=_init_command)

    preset_parser = subparsers.add_parser(
        "preset", help="Apply a feature preset to an existing workflow."
    )
    preset_parser.add_argument(
        "name",
        choices=(
            "feature-prd",
            "feature-plan",
            "feature-impl",
            "feature-design",
            "feature-release",
        ),
        help="Name of the preset to apply.",
    )
    preset_parser.add_argument(
        "--ticket",
        "--feature",
        dest="ticket",
        help="Ticket identifier to use when generating artefacts (legacy alias: --feature).",
    )
    preset_parser.add_argument(
        "--target",
        default=".",
        help="Directory containing the workflow project (default: current).",
    )
    preset_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing preset artefacts.",
    )
    preset_parser.add_argument(
        "--prompt-locale",
        choices=("ru", "en"),
        default="ru",
        help="Copy prompts in the specified locale into .claude/ (default: ru).",
    )
    preset_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without modifying files.",
    )
    preset_parser.set_defaults(func=_preset_command)

    smoke_parser = subparsers.add_parser(
        "smoke", help="Run the bundled smoke test to validate the workflow bootstrap."
    )
    smoke_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit verbose logs when running the smoke scenario.",
    )
    smoke_parser.set_defaults(func=_smoke_command)

    analyst_parser = subparsers.add_parser(
        "analyst-check",
        help="Validate the analyst dialog (Вопрос/Ответ) for the active feature PRD.",
    )
    analyst_parser.add_argument(
        "--ticket",
        "--feature",
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
        help="Directory containing the workflow project (default: current).",
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

    research_parser = subparsers.add_parser(
        "research",
        help="Collect scope and context for the Researcher agent.",
    )
    research_parser.add_argument(
        "--ticket",
        "--feature",
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
        help="Directory containing the workflow project (default: current).",
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
        "--feature",
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
        help="Directory containing the workflow project (default: current).",
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

    progress_parser = subparsers.add_parser(
        "progress",
        help="Check that docs/tasklist/<ticket>.md has new completed items after code changes.",
    )
    progress_parser.add_argument(
        "--ticket",
        "--feature",
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
        help="Directory containing the workflow project (default: current).",
    )
    progress_parser.add_argument(
        "--branch",
        help="Git branch name used to evaluate skip_branches (autodetected by default).",
    )
    progress_parser.add_argument(
        "--source",
        choices=("manual", "implement", "qa", "review", "gate"),
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
        help="Directory containing the workflow project (default: current).",
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
        help="Directory containing the workflow project (default: current).",
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
