import asyncio
import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "Smoke.scriv"
    document = project / "Files" / "Data" / "scene-uuid" / "content.rtf"
    document.parent.mkdir(parents=True)
    document.write_text(r"{\rtf1\ansi Smoke test manuscript.}", encoding="ascii")
    (project / "Smoke.scrivx").write_text(
        '<ScrivenerProject><Binder><BinderItem UUID="scene-uuid" Type="Text">'
        "<Title>Scene One</Title></BinderItem></Binder></ScrivenerProject>",
        encoding="utf-8",
    )
    return project


async def exercise_project(client: Client, project: Path) -> None:
    async with client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        assert {"open_project", "read_document", "search_project", "kb_add", "kb_query"} <= tools

        async def call(name: str, arguments: dict) -> str:
            result = await client.call_tool(name, arguments)
            assert not result.is_error, result
            return result.content[0].text

        assert "Opened project: Smoke" in await call("open_project", {"path": str(project)})
        assert "Smoke test manuscript." in await call("read_document", {"identifier": "Scene One"})
        assert "Scene One" in await call("search_project", {"query": "manuscript"})
        assert "Added to knowledge base" in await call(
            "kb_add", {"record_type": "character", "name": "Smoke Test Character"}
        )
        assert "Smoke Test Character" in await call(
            "kb_query", {"query_text": "Smoke Test Character"}
        )


@pytest.mark.parametrize("mode", ["2026-07-28", "legacy"])
def test_stdio_project_workflow(sample_project: Path, mode: str) -> None:
    server = StdioServerParameters(command=sys.executable, args=["-m", "scrivener_mcp.server"])
    asyncio.run(
        exercise_project(Client(server, mode=mode, read_timeout_seconds=5), sample_project)
    )
