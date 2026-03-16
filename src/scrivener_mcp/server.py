"""MCP Server for Scrivener projects."""

import argparse
import os
import platform
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .scrivener import ScrivenerProject

# Configure transport security to allow Docker and local connections
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "localhost",
        "localhost:8000",
        "127.0.0.1",
        "127.0.0.1:8000",
        "host.docker.internal",
        "host.docker.internal:8000",
        "0.0.0.0:8000",
    ],
)

# Initialize the MCP server
mcp = FastMCP("scrivener-mcp", transport_security=transport_security)

# Global project reference (set via environment or tool)
_project: ScrivenerProject | None = None

# Per-document (UUID) -> (mtime, size) when last read; cleared on open_project
_document_last_read: dict[str, tuple[float, int]] = {}


def get_common_scrivener_locations() -> list[Path]:
    """Get common locations where Scrivener projects might be stored."""
    home = Path.home()

    locations = [
        home / "Documents",
        home / "Scrivener",
        home / "Writing",
        home / "Dropbox",
        home / "Desktop",
    ]

    # Add platform-specific locations
    if platform.system() == "Darwin":  # macOS
        locations.extend([
            home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",  # iCloud
            home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Documents",
            home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Scrivener",
            home / "Documents" / "Sync files",  # Common sync folder (e.g. Drafts/Novel/*.scriv)
        ])
    elif platform.system() == "Windows":
        locations.extend([
            home / "OneDrive" / "Documents",
            home / "OneDrive",
        ])

    return [loc for loc in locations if loc.exists()]


def find_scriv_folders(search_path: Path, max_depth: int = 3) -> list[Path]:
    """Recursively find .scriv folders up to max_depth."""
    results = []

    try:
        for item in search_path.iterdir():
            if item.is_dir():
                if item.suffix == ".scriv":
                    # Verify it's a valid Scrivener project (has .scrivx file)
                    scrivx_files = list(item.glob("*.scrivx"))
                    if scrivx_files:
                        results.append(item)
                elif max_depth > 0 and not item.name.startswith("."):
                    # Recurse into subdirectories
                    results.extend(find_scriv_folders(item, max_depth - 1))
    except PermissionError:
        pass  # Skip directories we can't access

    return results


def _update_document_read_cache(project: ScrivenerProject, item) -> None:
    """Record that we read this document (by file mtime/size) for freshness checks."""
    global _document_last_read
    if not item.is_text:
        return
    path = project.get_content_path(item)
    if path.exists():
        stat = path.stat()
        _document_last_read[item.uuid] = (stat.st_mtime, stat.st_size)


def get_project() -> ScrivenerProject:
    """Get the current project, loading from SCRIVENER_PROJECT env var if needed."""
    global _project

    if _project is None:
        project_path = os.environ.get("SCRIVENER_PROJECT")
        if not project_path:
            raise ValueError(
                "No project loaded. Set SCRIVENER_PROJECT environment variable "
                "to the path of your .scriv folder, or use the open_project tool."
            )
        _project = ScrivenerProject(project_path)

    return _project


@mcp.tool()
def find_projects(search_path: str | None = None) -> str:
    """Find Scrivener projects on your computer.

    Searches common locations (Documents, Dropbox, iCloud, Documents/Sync files, etc.)
    up to six levels deep, so projects in nested folders (e.g. Drafts/Novel/*.scriv)
    are found. Use this to discover available projects, then use open_project to load one.

    Args:
        search_path: Optional folder to search (e.g. a project or sync folder).
                    If not provided, searches all common locations.

    Returns:
        List of found Scrivener projects with their paths.
    """
    projects = []

    if search_path:
        # Search specific path (e.g. project folder containing Draft/Book/*.scriv)
        search_dir = Path(search_path).expanduser().resolve()
        if search_dir.exists():
            projects = find_scriv_folders(search_dir, max_depth=6)
    else:
        # Search common locations (depth 6 to find nested Draft/Book/*.scriv)
        for location in get_common_scrivener_locations():
            projects.extend(find_scriv_folders(location, max_depth=6))

    if not projects:
        if search_path:
            return f"No Scrivener projects found in: {search_path}"
        return """No Scrivener projects found in common locations.

Try searching a specific folder:
  find_projects("/path/to/your/writing/folder")

Or open a project directly:
  open_project("/path/to/Your Novel.scriv")"""

    # Sort by name
    projects.sort(key=lambda p: p.name.lower())

    output = [f"Found {len(projects)} Scrivener project(s):\n"]

    for proj in projects:
        # Get basic info without fully loading the project
        name = proj.stem
        output.append(f"📚 {name}")
        output.append(f"   Path: {proj}")

    output.append("\n" + "=" * 40)
    output.append("To open a project, say: 'Open [project name]'")
    output.append("Or use: open_project(\"/path/to/project.scriv\")")

    return "\n".join(output)


@mcp.tool()
def open_project(path: str) -> str:
    """Open a Scrivener project.

    Args:
        path: Path to the .scriv folder

    Returns:
        Confirmation message with project info
    """
    global _project, _document_last_read

    project_path = Path(path).expanduser().resolve()
    _project = ScrivenerProject(project_path)
    _document_last_read.clear()

    # Check for lock
    lock_warning = ""
    if _project.is_locked:
        lock_warning = "\n⚠️  WARNING: Project appears to be open in Scrivener. Changes may conflict."

    # Count items
    total_items = sum(1 for _ in _project.all_items())
    text_items = sum(1 for item in _project.all_items() if item.is_text)

    return f"""Opened project: {_project.name}
Path: {_project.path}
Total items: {total_items}
Documents: {text_items}{lock_warning}

💡 **Tip:** Use `scan_project` to get a bird's eye view of the manuscript (chapter summaries, word counts, opening lines). This helps you understand the full project without reading every document."""


@mcp.tool()
def refresh_project() -> str:
    """Reload the project structure from disk without re-opening.

    Document text is always read fresh when you read a document or chapter.
    Only the binder (titles, new documents, moves, renames) is cached. Call this
    after you add/rename/move items in Scrivener so Claude sees the updated structure.
    """
    global _project
    if _project is None:
        return "No project open. Use open_project first."
    _project.reload_binder()
    return "Project structure refreshed. New and renamed items are now visible."


def _resolve_document(project: ScrivenerProject, identifier: str):
    """Resolve identifier (title, path, or UUID) to a single BinderItem, or None."""
    item = project.find_by_uuid(identifier)
    if not item:
        item = project.find_by_path(identifier)
    if not item:
        matches = project.find_by_title(identifier, exact=True)
        if len(matches) == 1:
            item = matches[0]
        elif len(matches) > 1:
            return None, "multiple"
    if not item:
        matches = project.find_by_title(identifier, exact=False)
        if len(matches) == 1:
            item = matches[0]
        elif len(matches) > 1:
            return None, "multiple"
    return (item, None) if item else (None, "not_found")


@mcp.tool()
def check_document_freshness(identifier: str) -> str:
    """Check whether a document has been modified since it was last read in this session.

    Use this when continuing a conversation after the user may have edited in Scrivener.
    If the document has changed, the tool will say so and you should re-read it to see
    the latest content before commenting.

    Args:
        identifier: Document title, path, or UUID (e.g. "Chapter 3", "Draft/Chapter 3/Scene 1")

    Returns:
        One of: document unchanged; document changed (re-read to see latest); not read yet; or error.
    """
    project = get_project()
    item, err = _resolve_document(project, identifier)
    if err == "multiple":
        return "Multiple documents match that identifier. Use the full path to specify which one."
    if err == "not_found" or item is None:
        return f"Document not found: {identifier}"

    if item.is_folder:
        return "That's a folder, not a document. Specify a document (e.g. a scene or chapter document) to check."

    path = project.get_content_path(item)
    if not path.exists():
        return f"No content file for: {item.title}"

    current = (path.stat().st_mtime, path.stat().st_size)
    last = _document_last_read.get(item.uuid)

    if last is None:
        return (
            f"📄 {item.title} has not been read yet in this session. "
            "Use read_document or read_chapter to load it, then I can track whether it changes."
        )

    if current != last:
        return (
            f"⚠️ **{item.title}** has been modified since it was last read. "
            "Re-read this document (or chapter) to see the latest content before commenting."
        )

    return f"✓ {item.title} — no changes since last read."


@mcp.tool()
def list_binder(folder_path: str | None = None) -> str:
    """List the binder structure of the Scrivener project.

    Shows the hierarchical structure of folders and documents, similar to
    Scrivener's binder sidebar.

    Args:
        folder_path: Optional path to a specific folder to list (e.g., "Neon Syn/Book One").
                    If not provided, lists the entire binder.

    Returns:
        Tree representation of the binder structure with:
        - 📁 for folders
        - 📄 for documents
        - ✓ for items marked "Include in Compile"
    """
    project = get_project()

    if folder_path:
        item = project.find_by_path(folder_path)
        if not item:
            # Try partial match
            matches = project.find_by_title(folder_path, exact=False)
            if matches:
                item = matches[0]

        if not item:
            return f"Folder not found: {folder_path}"

        return item.to_tree_string()

    return project.get_binder_tree()


@mcp.tool()
def read_document(identifier: str) -> str:
    """Read the content of a specific document.

    Args:
        identifier: Can be one of:
            - Document title (e.g., "Chapter 1")
            - Full path (e.g., "Neon Syn/Book One/Chapter 01/01")
            - UUID (e.g., "BA3D0D3E-0BC5-4E4F-AEB4-D7203A5215C4")

    Returns:
        The plain text content of the document, with metadata header showing
        title, path, and word count.
    """
    project = get_project()

    # Try to find by UUID first (most specific)
    item = project.find_by_uuid(identifier)

    # Try by exact path
    if not item:
        item = project.find_by_path(identifier)

    # Try by exact title
    if not item:
        matches = project.find_by_title(identifier, exact=True)
        if len(matches) == 1:
            item = matches[0]
        elif len(matches) > 1:
            # Multiple matches - return list
            paths = [f"  - {m.path}" for m in matches]
            return f"Multiple documents found with title '{identifier}':\n" + "\n".join(paths) + "\n\nPlease use the full path to specify which one."

    # Try by partial title
    if not item:
        matches = project.find_by_title(identifier, exact=False)
        if len(matches) == 1:
            item = matches[0]
        elif len(matches) > 1:
            paths = [f"  - {m.path}" for m in matches[:10]]
            more = f"\n  ... and {len(matches) - 10} more" if len(matches) > 10 else ""
            return f"Multiple documents match '{identifier}':\n" + "\n".join(paths) + more + "\n\nPlease use the full path to specify which one."

    if not item:
        return f"Document not found: {identifier}"

    if item.is_folder:
        # For folders, show contents
        child_count = sum(1 for _ in item.walk()) - 1
        text_count = sum(1 for c in item.walk() if c.is_text)
        word_count = project.get_word_count(item, recursive=True)

        return f"""📁 {item.title}
Path: {item.path}
Contains: {child_count} items ({text_count} documents)
Total words: {word_count:,}

Contents:
{item.to_tree_string()}"""

    # Read document content
    content = project.read_document(item)
    _update_document_read_cache(project, item)
    word_count = project.get_word_count(item)

    return f"""📄 {item.title}
Path: {item.path}
Words: {word_count:,}
Include in Compile: {"Yes" if item.include_in_compile else "No"}

---

{content}

---
💡 To check if this document was edited later: use check_document_freshness("{item.title}")."""


@mcp.tool()
def search_project(query: str, case_sensitive: bool = False) -> str:
    """Search for text across all documents in the project.

    Args:
        query: Text or regex pattern to search for
        case_sensitive: Whether to match case (default: False)

    Returns:
        List of matching documents with excerpts showing the matching lines.
    """
    project = get_project()
    results = project.search(query, case_sensitive=case_sensitive)

    if not results:
        return f"No matches found for: {query}"

    output = [f"Found {len(results)} document(s) matching '{query}':\n"]

    for item, matching_lines in results:
        output.append(f"\n📄 {item.path}")

        # Show up to 3 matching lines
        for line in matching_lines[:3]:
            # Truncate long lines
            if len(line) > 100:
                line = line[:100] + "..."
            output.append(f"   • {line}")

        if len(matching_lines) > 3:
            output.append(f"   ... and {len(matching_lines) - 3} more matches")

    return "\n".join(output)


@mcp.tool()
def get_word_counts(folder_path: str | None = None) -> str:
    """Get word count statistics for the project or a specific folder.

    Args:
        folder_path: Optional path to a specific folder. If not provided,
                    shows stats for the entire manuscript (Draft folder).

    Returns:
        Word count breakdown by folder/chapter.
    """
    project = get_project()

    if folder_path:
        item = project.find_by_path(folder_path)
        if not item:
            matches = project.find_by_title(folder_path, exact=False)
            item = matches[0] if matches else None

        if not item:
            return f"Folder not found: {folder_path}"

        root = item
    else:
        root = project.find_draft_folder()
        if not root:
            return "No Draft folder found in project."

    output = [f"Word counts for: {root.title}\n"]
    total = 0

    for item in root.walk():
        if item == root:
            continue

        if item.is_folder:
            folder_count = project.get_word_count(item, recursive=True)
            indent = "  " * (item.depth - root.depth - 1)
            output.append(f"{indent}📁 {item.title}: {folder_count:,} words")
        elif item.is_text:
            doc_count = project.get_word_count(item)
            indent = "  " * (item.depth - root.depth - 1)
            output.append(f"{indent}  📄 {item.title}: {doc_count:,} words")
            total += doc_count

    output.append(f"\n{'='*40}")
    output.append(f"Total: {total:,} words")

    return "\n".join(output)


@mcp.tool()
def read_chapter(chapter: str, include_titles: bool = True) -> str:
    """Read a specific chapter or section of the manuscript.

    Reads all documents within the specified chapter/folder, in binder order.

    ⚠️ For large projects, always read one chapter at a time to avoid timeouts.
    Use scan_project first to see available chapters.

    Args:
        chapter: Chapter name or path (e.g., "Chapter 01", "Book One/Chapter 05")
        include_titles: Whether to include document/folder titles as headings

    Returns:
        The chapter text with all its scenes/documents.
    """
    project = get_project()

    # Find the specific chapter
    item = project.find_by_path(chapter)
    if not item:
        matches = project.find_by_title(chapter, exact=False)
        item = matches[0] if matches else None

    if not item:
        return f"Chapter not found: {chapter}\n\n💡 Use scan_project or list_binder to see available chapters."

    # Read the chapter
    parts = []
    word_count = 0

    for child in item.walk():
        if child == item:
            if include_titles:
                parts.append(f"# {child.title}\n")
            continue

        if child.is_folder and include_titles:
            parts.append(f"\n{'#' * min(child.depth - item.depth + 1, 4)} {child.title}\n")
        elif child.is_text:
            content = project.read_document(child)
            _update_document_read_cache(project, child)
            if content:
                word_count += len(content.split())
                if include_titles:
                    parts.append(f"\n### {child.title}\n")
                parts.append(content)

    parts.append(f"\n---\n📊 Chapter word count: {word_count:,}")
    parts.append(
        '\n💡 To check if a document here was edited later: use check_document_freshness with its title.'
    )

    return "\n".join(parts)


@mcp.tool()
def get_synopsis(identifier: str) -> str:
    """Get the synopsis (short summary) of a document.

    In Scrivener, the synopsis is a brief description shown on index cards
    in corkboard view. Useful for understanding scene/chapter summaries.

    Args:
        identifier: Document title, path, or UUID

    Returns:
        The synopsis text, or a message if no synopsis exists.
    """
    project = get_project()

    # Find the document
    item = project.find_by_uuid(identifier)
    if not item:
        item = project.find_by_path(identifier)
    if not item:
        matches = project.find_by_title(identifier, exact=False)
        item = matches[0] if matches else None

    if not item:
        return f"Document not found: {identifier}"

    synopsis = project.read_synopsis(item)

    if not synopsis:
        return f"📄 {item.title}\nPath: {item.path}\n\nNo synopsis set for this document."

    return f"""📄 {item.title}
Path: {item.path}

Synopsis:
{synopsis}"""


@mcp.tool()
def get_notes(identifier: str) -> str:
    """Get the document notes (inspector notes) for a document.

    In Scrivener, document notes appear in the inspector panel and contain
    author notes, research, reminders, etc.

    Args:
        identifier: Document title, path, or UUID

    Returns:
        The notes text, or a message if no notes exist.
    """
    project = get_project()

    # Find the document
    item = project.find_by_uuid(identifier)
    if not item:
        item = project.find_by_path(identifier)
    if not item:
        matches = project.find_by_title(identifier, exact=False)
        item = matches[0] if matches else None

    if not item:
        return f"Document not found: {identifier}"

    notes = project.read_notes(item)

    if not notes:
        return f"📄 {item.title}\nPath: {item.path}\n\nNo notes for this document."

    return f"""📄 {item.title}
Path: {item.path}

Notes:
{notes}"""


@mcp.tool()
def scan_project(folder_path: str | None = None) -> str:
    """Scan the project and return a structured overview for analysis.

    Returns chapter titles, word counts, synopses (if any), and opening lines.
    This gives you enough context to understand the whole project without
    loading every document into memory.

    Use this to get a bird's eye view, then use read_document or
    read_chapter(chapter="...") to dive deeper into specific sections.

    Args:
        folder_path: Optional path to scan a specific folder (e.g., "Book One").
                    If not provided, scans the entire Draft/Manuscript folder.

    Returns:
        Structured overview with chapter summaries, word counts, and opening lines.
    """
    project = get_project()

    if folder_path:
        root = project.find_by_path(folder_path)
        if not root:
            matches = project.find_by_title(folder_path, exact=False)
            root = matches[0] if matches else None
        if not root:
            return f"Folder not found: {folder_path}"
    else:
        root = project.find_draft_folder()
        if not root:
            return "No Draft folder found in project."

    output = [f"# Project Overview: {root.title}\n"]

    # Get total stats
    total_words = project.get_word_count(root, recursive=True)
    total_docs = sum(1 for item in root.walk() if item.is_text)
    output.append(f"**Total:** {total_words:,} words across {total_docs} documents\n")
    output.append("---\n")

    def scan_item(item, depth=0):
        """Recursively scan an item and its children."""
        lines = []
        indent = "  " * depth

        if item.is_folder:
            folder_words = project.get_word_count(item, recursive=True)
            lines.append(f"{indent}## 📁 {item.title} ({folder_words:,} words)\n")

            # Check for folder synopsis
            synopsis = project.read_synopsis(item)
            if synopsis:
                lines.append(f"{indent}**Synopsis:** {synopsis[:200]}{'...' if len(synopsis) > 200 else ''}\n")

            # Process children
            for child in item.children:
                lines.extend(scan_item(child, depth + 1))

        elif item.is_text and item.include_in_compile:
            word_count = project.get_word_count(item)
            lines.append(f"{indent}### 📄 {item.title} ({word_count:,} words)")

            # Get synopsis if exists
            synopsis = project.read_synopsis(item)
            if synopsis:
                lines.append(f"{indent}**Synopsis:** {synopsis[:150]}{'...' if len(synopsis) > 150 else ''}")

            # Get opening line
            try:
                content = project.read_document(item)
                _update_document_read_cache(project, item)
                if content:
                    # Get first non-empty line, truncated
                    first_lines = [l.strip() for l in content.split('\n') if l.strip()]
                    if first_lines:
                        opening = first_lines[0][:120]
                        if len(first_lines[0]) > 120:
                            opening += "..."
                        lines.append(f"{indent}**Opens:** \"{opening}\"")
            except Exception:
                pass  # Skip if can't read

            lines.append("")  # Blank line between docs

        return lines

    # Scan all children of root
    for child in root.children:
        output.extend(scan_item(child))

    output.append("\n---")
    output.append("💡 **Tip:** Use `read_chapter(chapter=\"Chapter Name\")` to read a specific chapter in full.")

    return "\n".join(output)


def main():
    """Run the MCP server.

    Supports two transport modes:
    - stdio (default): For Claude Desktop and local MCP clients
    - streamable-http: For ChatGPT and remote HTTP clients

    Usage:
        scrivener-mcp              # stdio mode (Claude Desktop)
        scrivener-mcp --http       # HTTP mode on port 8000
        scrivener-mcp --http --port 9000  # HTTP mode on custom port
    """
    parser = argparse.ArgumentParser(
        description="MCP Server for Scrivener writing projects"
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run as HTTP server (for ChatGPT/remote clients) instead of stdio"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP server (default: 8000)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for HTTP server (default: 0.0.0.0)"
    )

    args = parser.parse_args()

    if args.http:
        # Set uvicorn host/port via environment variables
        os.environ["UVICORN_HOST"] = args.host
        os.environ["UVICORN_PORT"] = str(args.port)
        print(f"Starting Scrivener MCP server (HTTP) on {args.host}:{args.port}")
        mcp.run(transport="streamable-http")
    else:
        mcp.run()  # stdio transport for Claude Desktop


if __name__ == "__main__":
    main()
