from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path

import pytest

from scrivener_mcp.knowledge_base import (
    KnowledgeBaseConflictError,
    KnowledgeBaseError,
    add,
    get_kb_path,
    query,
    upsert_checkpoint,
)


def _worker_add_character(project_path: str, name: str, start_event) -> None:
    start_event.wait()
    add(Path(project_path), "character", name, attributes={"description": name})


def test_query_raises_on_corrupt_json(tmp_path: Path) -> None:
    project_path = tmp_path / "Novel.scriv"
    project_path.mkdir()
    kb_path = get_kb_path(project_path)
    kb_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(KnowledgeBaseError):
        query(project_path)


def test_upsert_checkpoint_reuses_existing_record(tmp_path: Path) -> None:
    project_path = tmp_path / "Novel.scriv"
    project_path.mkdir()

    first = upsert_checkpoint(
        project_path,
        "doc-uuid-1",
        "Scene One",
        attributes={"document_path": "Draft/Scene One", "reader_knows": "First pass"},
    )
    second = upsert_checkpoint(
        project_path,
        "doc-uuid-1",
        "Scene One",
        attributes={"document_path": "Draft/Scene One", "reader_knows": "Revised pass"},
        expected_revision=first["revision"],
    )

    checkpoints = query(project_path, type_filter="checkpoint")
    assert len(checkpoints) == 1
    assert checkpoints[0]["id"] == first["id"] == second["id"]
    assert checkpoints[0]["attributes"]["reader_knows"] == "Revised pass"
    assert "updated_at" in checkpoints[0]
    assert checkpoints[0]["revision"] == 2


def test_upsert_checkpoint_requires_expected_revision_for_existing_record(tmp_path: Path) -> None:
    project_path = tmp_path / "Novel.scriv"
    project_path.mkdir()

    upsert_checkpoint(
        project_path,
        "doc-uuid-1",
        "Scene One",
        attributes={"document_path": "Draft/Scene One", "reader_knows": "First pass"},
    )

    with pytest.raises(KnowledgeBaseConflictError):
        upsert_checkpoint(
            project_path,
            "doc-uuid-1",
            "Scene One",
            attributes={"document_path": "Draft/Scene One", "reader_knows": "Blind overwrite"},
        )


def test_upsert_checkpoint_rejects_stale_revision(tmp_path: Path) -> None:
    project_path = tmp_path / "Novel.scriv"
    project_path.mkdir()

    first = upsert_checkpoint(
        project_path,
        "doc-uuid-1",
        "Scene One",
        attributes={"document_path": "Draft/Scene One", "reader_knows": "First pass"},
    )
    upsert_checkpoint(
        project_path,
        "doc-uuid-1",
        "Scene One",
        attributes={"document_path": "Draft/Scene One", "reader_knows": "Second pass"},
        expected_revision=first["revision"],
    )

    with pytest.raises(KnowledgeBaseConflictError):
        upsert_checkpoint(
            project_path,
            "doc-uuid-1",
            "Scene One",
            attributes={"document_path": "Draft/Scene One", "reader_knows": "Stale third pass"},
            expected_revision=first["revision"],
        )


def test_concurrent_adds_preserve_both_records(tmp_path: Path) -> None:
    project_path = tmp_path / "Novel.scriv"
    project_path.mkdir()

    ctx = get_context("spawn")
    start_event = ctx.Event()
    processes = [
        ctx.Process(target=_worker_add_character, args=(str(project_path), "Alice", start_event)),
        ctx.Process(target=_worker_add_character, args=(str(project_path), "Bob", start_event)),
    ]

    for process in processes:
        process.start()

    start_event.set()

    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    characters = query(project_path, type_filter="character")
    assert sorted(record["name"] for record in characters) == ["Alice", "Bob"]
