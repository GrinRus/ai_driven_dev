from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aidd_runtime import active_state as _active_state
from aidd_runtime.io_utils import utc_timestamp

from aidd_runtime.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root as resolve_workspace_root

ACTIVE_STATE_FILE = Path("docs") / ".active.json"
PRD_TEMPLATE_FILE = Path("docs") / "prd" / "template.md"
PRD_DIR = Path("docs") / "prd"


def resolve_aidd_root(raw: Path) -> Path:
    """Resolve workflow root for any path inside the workspace."""
    _, project_root = resolve_workspace_root(raw, DEFAULT_PROJECT_SUBDIR)
    return project_root


@dataclass(frozen=True)
class FeatureIdentifiers:
    ticket: Optional[str] = None
    slug_hint: Optional[str] = None

    @property
    def resolved_ticket(self) -> Optional[str]:
        return (self.ticket or self.slug_hint or "").strip() or None

    @property
    def has_hint(self) -> bool:
        return bool((self.slug_hint or "").strip())


def read_identifiers(root: Path) -> FeatureIdentifiers:
    root = resolve_aidd_root(root)
    payload = _read_active_state_payload(root)
    ticket = _normalize_state_value(payload.get("ticket"))
    slug_hint = _normalize_state_value(payload.get("slug_hint"))
    if ticket:
        return FeatureIdentifiers(ticket=ticket, slug_hint=slug_hint)
    if slug_hint:
        # earlier setups used slug as primary identifier
        return FeatureIdentifiers(ticket=slug_hint, slug_hint=slug_hint)
    return FeatureIdentifiers(ticket=None, slug_hint=slug_hint)


def read_active_state(root: Path) -> ActiveState:
    root = resolve_aidd_root(root)
    payload = _read_active_state_payload(root)
    return ActiveState(
        ticket=_normalize_state_value(payload.get("ticket")),
        slug_hint=_normalize_state_value(payload.get("slug_hint")),
        stage=_normalize_state_value(payload.get("stage")),
        work_item=_normalize_state_value(payload.get("work_item")),
        last_review_report_id=_normalize_state_value(payload.get("last_review_report_id")),
        updated_at=_normalize_state_value(payload.get("updated_at")),
    )


def write_active_state(
    root: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
    stage: Optional[str] = None,
    work_item: Optional[str] = None,
) -> ActiveState:
    root = resolve_aidd_root(root)
    current = read_active_state(root)
    current_payload = _read_active_state_payload(root)
    ticket_value = (ticket if ticket is not None else current.ticket) or ""
    slug_value = (slug_hint if slug_hint is not None else current.slug_hint) or ""
    stage_value = (stage if stage is not None else current.stage) or ""
    requested_work_item = (work_item if work_item is not None else current.work_item) or ""
    work_item_value, report_id = _active_state.normalize_work_item_for_stage(
        stage=stage_value,
        requested_work_item=requested_work_item,
        current_work_item=current.work_item,
    )
    if work_item is None and not requested_work_item and current.work_item:
        work_item_value = current.work_item

    last_review_report_id = _normalize_state_value(current_payload.get("last_review_report_id"))
    if report_id:
        last_review_report_id = report_id

    payload = {
        "ticket": ticket_value or None,
        "slug_hint": slug_value or None,
        "stage": stage_value or None,
        "work_item": work_item_value or None,
        "last_review_report_id": last_review_report_id or None,
        "updated_at": utc_timestamp(),
    }
    path = root / ACTIVE_STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return read_active_state(root)


def resolve_identifiers(
    root: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> FeatureIdentifiers:
    stored = read_identifiers(root)
    resolved_ticket = (ticket or "").strip() or stored.resolved_ticket
    if slug_hint is None:
        resolved_hint = stored.slug_hint
    else:
        resolved_hint = slug_hint.strip() or None
    return FeatureIdentifiers(ticket=resolved_ticket, slug_hint=resolved_hint)


def scaffold_prd(root: Path, ticket: str) -> bool:
    """Ensure docs/prd/<ticket>.prd.md exists by copying the template."""

    root = resolve_aidd_root(root)
    ticket_value = ticket.strip()
    if not ticket_value:
        return False

    template_path = root / PRD_TEMPLATE_FILE
    prd_path = root / PRD_DIR / f"{ticket_value}.prd.md"

    if not template_path.exists() or prd_path.exists():
        return False

    try:
        content = template_path.read_text(encoding="utf-8")
    except OSError:
        return False

    content = content.replace("<ticket>", ticket_value)
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prd_path.write_text(content, encoding="utf-8")
    except OSError:
        return False

    return True


def write_identifiers(
    root: Path,
    *,
    ticket: str,
    slug_hint: Optional[str] = None,
    scaffold_prd_file: bool = True,
) -> None:
    root = resolve_aidd_root(root)
    ticket_value = ticket.strip()
    if not ticket_value:
        raise ValueError("ticket must be a non-empty string")

    stored = read_active_state(root)
    if slug_hint is None:
        hint_value = None
    else:
        # Accept only a compact slug token and ignore trailing note/answers text.
        hint_value = _active_state.normalize_slug_hint_token(slug_hint) or None
    if not hint_value and stored.slug_hint and (stored.ticket or stored.slug_hint) == ticket_value:
        hint_value = stored.slug_hint
    if not hint_value:
        hint_value = ticket_value

    write_active_state(root, ticket=ticket_value, slug_hint=hint_value)

    if scaffold_prd_file:
        scaffold_prd(root, ticket_value)


def _read_active_state_payload(root: Path) -> dict:
    path = root / ACTIVE_STATE_FILE
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_state_value(value: object) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


@dataclass(frozen=True)
class ActiveState:
    ticket: Optional[str] = None
    slug_hint: Optional[str] = None
    stage: Optional[str] = None
    work_item: Optional[str] = None
    last_review_report_id: Optional[str] = None
    updated_at: Optional[str] = None
