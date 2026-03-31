# Scrivener MCP

A read-only MCP server that connects MCP-capable assistants to your Scrivener writing projects.

Work in Scrivener, ask your assistant for help. It can see your project structure, content, notes, and synopses, while all writing stays in Scrivener where it belongs.

## What can it do?

Point your MCP client at your novel and ask:
- "Scan the project and give me an overview"
- "Find inconsistencies in my character descriptions"
- "What plot threads are unresolved?"
- "Where do I mention the lighthouse?"
- "What's my word count by chapter?"
- "Read Chapter 3"

## Supported Platforms

| Platform | Client | Status |
|----------|--------|--------|
| macOS | Claude Desktop | Supported |
| Windows | Claude Desktop | Supported |
| macOS | Local MCP client (for example, Codex) | Expected to work via `stdio` |
| Windows | Local MCP client (for example, Codex) | Expected to work via `stdio` |

## Requirements

- Python 3.10+
- Scrivener 3 project (.scriv folder)
- An MCP client such as Claude Desktop or Codex

## Installation

```bash
# Clone the repo
git clone https://github.com/zaphodsdad/scrivener-mcp.git
cd scrivener-mcp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
```

## Setup with Claude Desktop

Add to your config file:
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "scrivener": {
      "command": "/path/to/scrivener-mcp/.venv/bin/scrivener-mcp"
    }
  }
}
```

Restart Claude Desktop. That's it.

## Setup with Codex or another local MCP client

Use the same command-line entry point as a local `stdio` MCP server:

```bash
/path/to/scrivener-mcp/.venv/bin/scrivener-mcp
```

If your client supports command-based local MCP servers, point it at that executable. The server defaults to `stdio`, which is the same mode used by Claude Desktop.

## Remote HTTP mode

For clients that need a remote MCP endpoint instead of local `stdio`, run:

```bash
scrivener-mcp --http
```

Optional:

- `--host 127.0.0.1`
- `--port 9000`
- `SCRIVENER_MCP_ALLOWED_HOSTS="localhost:9000,127.0.0.1:9000"` to allow additional host headers for HTTP deployments

## Finding your projects

The server searches **Documents**, **Dropbox**, **Desktop**, **iCloud**, and (on macOS) **Documents/Sync files**, up to six levels deep—so projects inside nested folders like `Drafts/Novel/*.scriv` or `Book/MyNovel.scriv` are found automatically.

If your projects live elsewhere, run **find_projects** with a path, for example:

- `find_projects("/Users/you/Documents/Sync files/Miranda")`  
- `find_projects("/path/to/your/writing/folder")`

Then use **open_project** with the full path of the `.scriv` folder (e.g. from the find list) to open a project.

## Available Tools (21)

| Tool | Description |
|------|-------------|
| `find_projects` | Scan common locations for Scrivener projects |
| `open_project` | Open a Scrivener project by path |
| `refresh_project` | Reload binder structure from disk (use after adding/renaming in Scrivener) |
| `check_document_freshness` | Check if a document was modified since last read (prompts re-read when changed) |
| `scan_project` | Get bird's eye view: chapter titles, word counts, synopses, opening lines |
| `list_binder` | Show the binder structure (folders and documents) |
| `read_document` | Read a single document by title, path, or UUID |
| `read_chapter` | Read a full chapter with all its scenes |
| `search_project` | Full-text search across all documents |
| `get_word_counts` | Word count statistics by chapter/folder |
| `get_synopsis` | Read the synopsis (index card text) for a document |
| `get_notes` | Read the inspector notes for a document |
| **Knowledge base** | |
| `kb_add` | Add a character, location, event, checkpoint, or fixed fact to the project knowledge base (use only after user confirms) |
| `kb_query` | Query the knowledge base by type or text |
| `kb_list_types` | List knowledge base counts by type |
| `kb_list_fixed_facts` | List fixed facts (atomic story-world truths), optionally filtered by text |
| `kb_add_section_checkpoint` | Add/update a section checkpoint (UUID-backed) from a document identifier |
| `kb_revision_brief` | Revision startup: previous-section reader state + relevant fixed facts (by entities) |
| `kb_suggest_entities` | Suggest canonical entity names from KB (characters/locations) |
| `kb_get_reader_checkpoint_before` | Get the previous section's reader_knows only (orientation-safe when rewriting earlier sections) |
| `kb_get_checkpoints_ordered` | List all checkpoints in draft (binder) order |

## Recommended Workflow

1. **Open project:** "Open my Scrivener project Neon Syn"
2. **Scan for overview:** "Scan the project" - gives chapter summaries without loading everything
3. **Dive deeper:** "Read Chapter 3" - read specific chapters as needed
4. **Search:** "Search for mentions of the red door" - searches all documents
5. **After editing in Scrivener:** Your latest text is seen on the next read. If you added/renamed documents, say "Refresh the project" so the structure updates

## Example Prompts

- "Find my Scrivener projects"
- "Open [project name]"
- "Scan the project and summarize each chapter"
- "Read Chapter 1"
- "Search for mentions of 'lighthouse'"
- "What's my word count by chapter?"
- "Show me the synopsis for Chapter 3"
- "Find plot holes based on the chapter summaries"
- "Refresh the project" (after adding or renaming items in Scrivener)
- "Check if Chapter 3 has changed" or "Did I change that document since you last read it?"
- "Add the character Maria to the knowledge base" (the assistant should suggest first, then add when you agree)
- "What do we have in the knowledge base for characters?"

## Knowledge base

A structured store (characters, locations, events, checkpoints, fixed facts) lives in a JSON file **alongside** your `.scriv` folder (e.g. `MyNovel-kb.json`). The assistant can query it and, **only after you confirm**, add entries when it spots new characters or key facts. Use it for consistency checks and to avoid re-reading the whole manuscript for simple lookups. For document and project versioning, use Scrivener’s built-in snapshots and versioning.

### Checkpoint records and orientation

You can store **checkpoints** per section: a short synopsis and "what the reader knows so far" (`reader_knows`). Use them so that when working on section N+1, the assistant only sees reader state from the **previous** section (N), never from later sections, so orientation stays correct even if you rewrite an earlier section.

- **Convention:** `record_type="checkpoint"`, `attributes`: `document_path`, optional `order`, `synopsis`, `reader_knows`; `source` = document UUID (recommended) or document path (used to match/upsert). Adding a checkpoint with the same `source` updates the existing one (one checkpoint per document).
- **`kb_get_reader_checkpoint_before(identifier)`** — Returns the `reader_knows` text from the section **immediately before** the given document in draft order. Call it when starting a pass on a section so you only get "what the reader knew at the start of this section."
- **`kb_get_checkpoints_ordered()`** — Returns all checkpoints in **binder (draft) order** (position, path, synopsis, truncated reader_knows). Order is computed from the current project so it stays correct after reordering.
- **`kb_add_section_checkpoint(identifier, synopsis, reader_knows)`** — Convenience helper that writes a UUID-backed section checkpoint with `document_path` filled in.
- **`kb_revision_brief(identifier, entities=[...])`** — One-call revision startup: previous-section reader orientation + fixed facts touching the given entities (and their `downstream_references` when present).

### Fixed facts (downstream continuity)

For downstream implication tracking and continuity, you can store **fixed facts**: small, atomic story-world truths that later sections should not contradict (even if the reader doesn’t learn them until later).

- **Convention:** `record_type="fixed_fact"`. Suggested attributes: `fact` (1–3 sentences), `entities` (list of strings), optional `introduced_in_document_path`, `evidence`, `sensitivity` (`"hard"` or `"soft"`), `status` (`"active"` or `"retconned"`), and optional `downstream_references` (list of binder document paths where the fact is relied upon later).
- **Usage:** Before rewriting a section, the assistant can query `fixed_fact` records relevant to the entities in that section and flag contradictions or downstream impacts without rereading the whole manuscript.

**Entity naming convention:** For `fixed_fact.attributes.entities`, use canonical names (the `name` field) from KB `character`/`location` records. Use `kb_suggest_entities(query_text)` to find the canonical name.

## How It Works

Scrivener projects are folders containing:
- A `.scrivx` XML file (the binder structure)
- RTF files for each document (`Files/Data/{UUID}/content.rtf`)

This server parses the XML to understand your project structure, then reads and converts the RTF files to plain text for the assistant to analyze.

## Why Read-Only?

Scrivener is excellent software. Write in Scrivener. Use this MCP to give your assistant context about your work so it can help you think through problems, find inconsistencies, and answer questions about your manuscript.

All writing stays in Scrivener where it belongs.

## Stale view and refresh

- **Document text** is read from disk every time you read a document or chapter, so edits in Scrivener are visible on the next read.
- **Binder structure** (titles, new documents, moves, renames) is cached when you open the project. After you add or rename items in Scrivener, use **refresh_project** so the MCP client sees the updated structure. You do not need to re-open or re-type the path.
- **Freshness check:** When you return to a chat after editing in Scrivener, the assistant can call **check_document_freshness** (e.g. for the chapter you were discussing). If the file has changed since it was last read, the tool tells it to re-read before commenting, so you don’t get feedback on outdated text.

## Limitations

- Scrivener 3 format only (Scrivener 1/2 not tested)
- Some RTF formatting may not convert perfectly
- **Manuscript read-only:** The MCP does not edit your Scrivener documents or binder. It can write to the **knowledge base** (sibling JSON file) and run **versioning** (Git commits or draft save/restore) when you ask

## Related Projects

- [prose-pipeline](https://github.com/zaphodsdad/prose-pipeline) - AI-powered prose generation

## License

MIT
