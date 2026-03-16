# Scrivener MCP

A read-only MCP server that connects Claude Desktop to your Scrivener writing projects.

Work in Scrivener, ask Claude for help. Claude can see your entire project - structure, content, notes, synopses - but all writing happens in Scrivener where it belongs.

## What can it do?

Point Claude at your novel and ask:
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

## Requirements

- Python 3.10+
- Scrivener 3 project (.scriv folder)
- Claude Desktop

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

## Finding your projects

The server searches **Documents**, **Dropbox**, **Desktop**, **iCloud**, and (on macOS) **Documents/Sync files**, up to six levels deep—so projects inside nested folders like `Drafts/Novel/*.scriv` or `Book/MyNovel.scriv` are found automatically.

If your projects live elsewhere, run **find_projects** with a path, for example:

- `find_projects("/Users/you/Documents/Sync files/Miranda")`  
- `find_projects("/path/to/your/writing/folder")`

Then use **open_project** with the full path of the `.scriv` folder (e.g. from the find list) to open a project.

## Available Tools (12)

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

## How It Works

Scrivener projects are folders containing:
- A `.scrivx` XML file (the binder structure)
- RTF files for each document (`Files/Data/{UUID}/content.rtf`)

This server parses the XML to understand your project structure, then reads and converts the RTF files to plain text for Claude to analyze.

## Why Read-Only?

Scrivener is excellent software. Write in Scrivener. Use this MCP to give Claude context about your work so it can help you think through problems, find inconsistencies, and answer questions about your manuscript.

All writing stays in Scrivener where it belongs.

## Stale view and refresh

- **Document text** is read from disk every time you read a document or chapter, so edits in Scrivener are visible on the next read.
- **Binder structure** (titles, new documents, moves, renames) is cached when you open the project. After you add or rename items in Scrivener, use **refresh_project** so Claude sees the updated structure. You do not need to re-open or re-type the path.
- **Freshness check:** When you return to a chat after editing in Scrivener, Claude can call **check_document_freshness** (e.g. for the chapter you were discussing). If the file has changed since it was last read, the tool tells Claude to re-read before commenting, so you don’t get feedback on outdated text.

## Limitations

- Scrivener 3 format only (Scrivener 1/2 not tested)
- Some RTF formatting may not convert perfectly
- **Read-only by design** — this MCP has no write tools; it cannot modify your project or break its structure

## Related Projects

- [prose-pipeline](https://github.com/zaphodsdad/prose-pipeline) - AI-powered prose generation

## License

MIT
