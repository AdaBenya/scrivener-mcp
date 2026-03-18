# Scrivener MCP Server

A read-only MCP server that gives Claude Desktop access to Scrivener writing projects.

## Project Vision

Allow writers to work in Scrivener while Claude reads their project to help with:
- "Scan the project and summarize each chapter"
- "Find plot holes in my novel"
- "Check character consistency across chapters"
- "What's my word count by chapter?"
- "Search for everywhere I mention the red door"

**Philosophy:** Write in Scrivener. Ask Claude for help. All writing stays in Scrivener.

## Implemented MCP Tools (21)

| Tool | Description |
|------|-------------|
| `find_projects` | Scan common locations for .scriv projects |
| `open_project` | Load a Scrivener project by path |
| `refresh_project` | Reload binder structure from disk |
| `check_document_freshness` | Check if a document was modified since last read; re-read if so |
| `scan_project` | Bird's eye view: chapter titles, word counts, synopses, opening lines |
| `list_binder` | Show project structure as tree |
| `read_document` | Read a single document by title, path, or UUID |
| `read_chapter` | Read a full chapter with all its scenes |
| `search_project` | Full-text search across all documents |
| `get_word_counts` | Word count stats per document/folder |
| `get_synopsis` | Read the synopsis (index card text) for a document |
| `get_notes` | Read the inspector notes for a document |
| `kb_add` | Add character/location/event/checkpoint/fixed_fact to knowledge base — **only after user confirms** |
| `kb_query` | Query knowledge base by type or text |
| `kb_list_types` | List knowledge base counts by type |
| `kb_list_fixed_facts` | List fixed facts (atomic story-world truths), optionally filtered by text |
| `kb_add_section_checkpoint` | Add/update a section checkpoint (UUID-backed) from a document identifier |
| `kb_revision_brief` | Revision startup: previous-section reader state + relevant fixed facts (by entities) |
| `kb_suggest_entities` | Suggest canonical entity names from KB (characters/locations) |
| `kb_get_reader_checkpoint_before` | Get previous section's reader_knows only (orientation-safe) |
| `kb_get_checkpoints_ordered` | List all checkpoints in draft (binder) order |

**Stale view:** Document text is read from disk on every read. Use `refresh_project` after adding/renaming. When the user returns after editing, call `check_document_freshness`; if changed, re-read before answering.

**Knowledge base:** Stored in a JSON file alongside the .scriv (e.g. MyNovel-kb.json). Suggest additions when you spot characters, locations, or key events; call `kb_add` only after the user agrees. For versioning, use Scrivener’s built-in snapshots.

**Checkpoints:** Use `record_type="checkpoint"` with attributes `document_path`, optional `order`, `synopsis`, `reader_knows`; `source` = document UUID (recommended; stable across renames/moves) or path (upsert by document). `kb_get_reader_checkpoint_before(identifier)` returns only the **previous** section's `reader_knows`—so "reader knows" is always from sections before the current one and orientation stays correct when rewriting earlier sections. `kb_get_checkpoints_ordered()` lists all checkpoints in binder order. `kb_add_section_checkpoint(identifier, synopsis, reader_knows)` is the easiest way to write a UUID-backed section checkpoint.

**Fixed facts:** Use `record_type="fixed_fact"` to store atomic, citable story-world truths (1–3 sentence `fact` plus optional `entities`, evidence, sensitivity, status, and optional `downstream_references` (a list of binder document paths where the fact is relied upon later)). Query these before/after rewrites to spot downstream continuity breaks without rereading the whole manuscript. For `entities`, use canonical KB names (character/location `name`); use `kb_suggest_entities(query_text)` to find canonical spellings.

## Technical Details

### Scrivener File Format

A `.scriv` file is actually a folder (package on Mac):
```
MyNovel.scriv/
├── Files/
│   └── Data/
│       ├── {UUID}/
│       │   ├── content.rtf    # The actual text
│       │   └── synopsis.txt   # Optional synopsis
│       └── ...
├── Settings/
│   └── ...
├── Snapshots/
│   └── ...
└── project.scrivx             # XML binder structure
```

### How It Works

1. Parses the `.scrivx` XML to reconstruct binder structure
2. Reads RTF files from `Files/Data/{UUID}/content.rtf`
3. Converts RTF to plain text using `striprtf` library
4. Returns text to Claude for analysis

## Project Structure

```
scrivener-mcp/
├── src/
│   └── scrivener_mcp/
│       ├── __init__.py
│       ├── server.py          # MCP server + all tools
│       ├── knowledge_base.py  # KB add/query (JSON alongside .scriv)
│       └── scrivener/
│           ├── __init__.py
│           ├── project.py     # ScrivenerProject class
│           ├── binder.py      # Binder/BinderItem parsing
│           └── rtf.py          # RTF conversion utilities
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## Dependencies

```
mcp                 # Official MCP SDK
striprtf            # RTF to text conversion
```

## Quick Start (Mac)

```bash
# Clone and setup
git clone https://github.com/zaphodsdad/scrivener-mcp.git
cd scrivener-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Test it runs
scrivener-mcp  # Ctrl+C to exit
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

```json
{
  "mcpServers": {
    "scrivener": {
      "command": "/path/to/scrivener-mcp/.venv/bin/scrivener-mcp"
    }
  }
}
```

Restart Claude Desktop. Ask things like:
- "Find my Scrivener projects"
- "Open Neon Syn"
- "Scan the project"
- "Read Chapter 5"
- "Search for mentions of the red door"
- "What's my word count by chapter?"

## Recommended Workflow

1. **Open:** "Open my project [name]"
2. **Scan:** "Scan the project" - get overview without loading everything
3. **Dive deep:** "Read Chapter 3" - read specific chapters
4. **Search:** "Search for [term]" - find across all documents
5. **Refresh:** "Re-open the project" - after editing in Scrivener

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [striprtf](https://pypi.org/project/striprtf/)
- [Scrivener File Format](https://preservation.tylerthorsted.com/2025/03/21/scrivener/)

## Related Projects

- [prose-pipeline](https://github.com/zaphodsdad/prose-pipeline) - AI-powered prose generation
