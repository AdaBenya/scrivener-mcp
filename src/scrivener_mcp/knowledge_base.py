"""Structured knowledge base for a Scrivener project (characters, locations, events).

Stored alongside the .scriv folder as a single JSON file (e.g. MyNovel-kb.json).
RAG-ready: schema supports a content/notes field for future embedding index.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def get_kb_path(project_path: Path) -> Path:
    """Path to the knowledge base file: sibling of .scriv, e.g. MyNovel-kb.json."""
    # project_path is the .scriv directory; stem is the project name without .scriv
    name = project_path.name  # e.g. "MyNovel.scriv"
    base = name.replace(".scriv", "") if name.endswith(".scriv") else name
    return project_path.parent / f"{base}-kb.json"


class KnowledgeBaseError(RuntimeError):
    """Raised when the sidecar knowledge base cannot be read or written safely."""


class KnowledgeBaseConflictError(KnowledgeBaseError):
    """Raised when a write is based on a stale or missing record revision."""

    def __init__(self, message: str, current_record: dict[str, Any] | None = None):
        super().__init__(message)
        self.current_record = current_record


def _get_lock_path(path: Path) -> Path:
    """Lock file used to serialize KB reads/writes across processes."""
    return path.with_name(f"{path.name}.lock")


def _acquire_file_lock(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        lock_file.write(b"0")
        lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _release_file_lock(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _locked_records(path: Path) -> Iterator[None]:
    lock_path = _get_lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        _acquire_file_lock(lock_file)
        try:
            yield
        finally:
            _release_file_lock(lock_file)


def _load_records_unlocked(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeBaseError(f"Could not read knowledge base at {path}: {exc}") from exc

    if not data.strip():
        return []

    try:
        records = json.loads(data)
    except json.JSONDecodeError as exc:
        raise KnowledgeBaseError(
            f"Knowledge base at {path} is not valid JSON. "
            "Please restore it from backup or fix the file before writing again."
        ) from exc

    if not isinstance(records, list):
        raise KnowledgeBaseError(
            f"Knowledge base at {path} must contain a JSON list of records."
        )

    return [_normalize_record(record) for record in records]


def _record_revision(record: dict[str, Any]) -> int:
    revision = record.get("revision")
    return revision if isinstance(revision, int) and revision >= 1 else 1


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized["revision"] = _record_revision(normalized)
    return normalized


def _save_records_unlocked(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(records, indent=2, ensure_ascii=False)

    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except UnboundLocalError:
            pass
        except OSError:
            pass
        raise KnowledgeBaseError(f"Could not write knowledge base at {path}: {exc}") from exc


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
    with _locked_records(path):
        records = _load_records_unlocked(path)
        record = {
            "id": str(uuid.uuid4()),
            "type": type_.strip().lower() or "other",
            "name": name.strip(),
            "attributes": dict(attributes or {}),
            "source": source.strip() if source else None,
            "revision": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)
        _save_records_unlocked(path, records)
        return record


def upsert_checkpoint(
    project_path: Path,
    source: str,
    name: str,
    attributes: dict[str, Any] | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Update existing checkpoint with same source, or add new one.

    Used so there is at most one checkpoint per document (by source).
    """
    path = get_kb_path(project_path)
    source_stripped = source.strip() if source else ""
    attrs = dict(attributes or {})

    with _locked_records(path):
        records = _load_records_unlocked(path)

        for i, r in enumerate(records):
            if (
                r.get("type") == "checkpoint"
                and (
                    r.get("source") == source_stripped
                    or (r.get("attributes") or {}).get("document_path") == source_stripped
                )
            ):
                current_revision = _record_revision(r)
                if expected_revision is None:
                    raise KnowledgeBaseConflictError(
                        "Checkpoint already exists and requires expected_revision for updates.",
                        current_record=r,
                    )
                if expected_revision != current_revision:
                    raise KnowledgeBaseConflictError(
                        f"Checkpoint revision conflict: expected {expected_revision}, "
                        f"current is {current_revision}.",
                        current_record=r,
                    )
                records[i] = {
                    **r,
                    "name": name.strip(),
                    "attributes": attrs,
                    "revision": current_revision + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                _save_records_unlocked(path, records)
                return records[i]

        if expected_revision not in (None, 0):
            raise KnowledgeBaseConflictError(
                f"Checkpoint does not exist yet, so expected_revision must be omitted or 0 "
                f"(received {expected_revision})."
            )
        record = {
            "id": str(uuid.uuid4()),
            "type": "checkpoint",
            "name": name.strip(),
            "attributes": attrs,
            "source": source_stripped or None,
            "revision": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)
        _save_records_unlocked(path, records)
        return record


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
    with _locked_records(path):
        records = _load_records_unlocked(path)

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
    with _locked_records(path):
        records = _load_records_unlocked(path)
    counts: dict[str, int] = {}
    for r in records:
        t = r.get("type") or "other"
        counts[t] = counts.get(t, 0) + 1
    return counts
