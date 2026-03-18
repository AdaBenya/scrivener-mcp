"""Structured knowledge base for a Scrivener project (characters, locations, events).

Stored alongside the .scriv folder as a single JSON file (e.g. MyNovel-kb.json).
RAG-ready: schema supports a content/notes field for future embedding index.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_kb_path(project_path: Path) -> Path:
    """Path to the knowledge base file: sibling of .scriv, e.g. MyNovel-kb.json."""
    # project_path is the .scriv directory; stem is the project name without .scriv
    name = project_path.name  # e.g. "MyNovel.scriv"
    base = name.replace(".scriv", "") if name.endswith(".scriv") else name
    return project_path.parent / f"{base}-kb.json"


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = path.read_text(encoding="utf-8")
        if not data.strip():
            return []
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return []


def _save_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add(
    project_path: Path,
    type_: str,
    name: str,
    attributes: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Add a record to the project knowledge base.

    Args:
        project_path: Path to the .scriv folder.
        type_: One of character, location, event, other.
        name: Display name/title for the record.
        attributes: Optional dict (e.g. description, first_seen, dates).
        source: Optional document path or UUID where this was found.

    Returns:
        The created record (with id, created_at).
    """
    path = get_kb_path(project_path)
    records = _load_records(path)
    record = {
        "id": str(uuid.uuid4()),
        "type": type_.strip().lower() or "other",
        "name": name.strip(),
        "attributes": dict(attributes or {}),
        "source": source.strip() if source else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    records.append(record)
    _save_records(path, records)
    return record


def upsert_checkpoint(
    project_path: Path,
    source: str,
    name: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update existing checkpoint with same source, or add new one.

    Used so there is at most one checkpoint per document (by source).
    """
    path = get_kb_path(project_path)
    records = _load_records(path)
    source_stripped = source.strip() if source else ""
    attrs = dict(attributes or {})

    for i, r in enumerate(records):
        if (r.get("type") == "checkpoint" and
                (r.get("source") == source_stripped or
                 (r.get("attributes") or {}).get("document_path") == source_stripped)):
            records[i] = {
                **r,
                "name": name.strip(),
                "attributes": attrs,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _save_records(path, records)
            return records[i]

    return add(project_path, "checkpoint", name, attributes=attrs, source=source_stripped or None)


def query(
    project_path: Path,
    type_filter: str | None = None,
    query_text: str | None = None,
) -> list[dict[str, Any]]:
    """Query the knowledge base.

    Args:
        project_path: Path to the .scriv folder.
        type_filter: If set, only return records of this type (character, location, event, other).
        query_text: If set, filter records whose name or attributes contain this string (case-insensitive).

    Returns:
        List of matching records.
    """
    path = get_kb_path(project_path)
    records = _load_records(path)

    if type_filter:
        t = type_filter.strip().lower()
        records = [r for r in records if r.get("type") == t]

    if query_text:
        q = query_text.strip().lower()
        def matches(r: dict[str, Any]) -> bool:
            if q in (r.get("name") or "").lower():
                return True
            for v in (r.get("attributes") or {}).values():
                if isinstance(v, str) and q in v.lower():
                    return True
                if isinstance(v, (list, tuple)):
                    for item in v:
                        if isinstance(item, str) and q in item.lower():
                            return True
            return False
        records = [r for r in records if matches(r)]

    return records


def list_types(project_path: Path) -> dict[str, int]:
    """Return counts per type (character, location, event, other).

    Args:
        project_path: Path to the .scriv folder.

    Returns:
        Dict mapping type name to count.
    """
    path = get_kb_path(project_path)
    records = _load_records(path)
    counts: dict[str, int] = {}
    for r in records:
        t = r.get("type") or "other"
        counts[t] = counts.get(t, 0) + 1
    return counts
