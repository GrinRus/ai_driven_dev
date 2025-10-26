from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ACTIVE_TICKET_FILE = Path("docs") / ".active_ticket"
SLUG_HINT_FILE = Path("docs") / ".active_feature"


def _read_text(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


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
    root = root.resolve()
    ticket = _read_text(root / ACTIVE_TICKET_FILE)
    slug_hint = _read_text(root / SLUG_HINT_FILE)
    if ticket:
        return FeatureIdentifiers(ticket=ticket, slug_hint=slug_hint)
    if slug_hint:
        # legacy setups used slug as primary identifier
        return FeatureIdentifiers(ticket=slug_hint, slug_hint=slug_hint)
    return FeatureIdentifiers(ticket=None, slug_hint=slug_hint)


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


def write_identifiers(
    root: Path,
    *,
    ticket: str,
    slug_hint: Optional[str] = None,
) -> None:
    root = root.resolve()
    ticket_value = ticket.strip()
    if not ticket_value:
        raise ValueError("ticket must be a non-empty string")

    stored = read_identifiers(root)

    ticket_path = root / ACTIVE_TICKET_FILE
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    ticket_path.write_text(ticket_value, encoding="utf-8")

    if slug_hint is None:
        if stored.slug_hint and (stored.ticket or stored.slug_hint) == ticket_value:
            hint_value = stored.slug_hint
        else:
            hint_value = None
    else:
        hint_value = slug_hint.strip() or None
    if not hint_value:
        hint_value = ticket_value

    hint_path = root / SLUG_HINT_FILE
    hint_path.parent.mkdir(parents=True, exist_ok=True)
    hint_path.write_text(hint_value, encoding="utf-8")
