# gdoc-comments MCP server

An MCP server for reading/editing Google Docs content and managing comments
(list, create, reply, resolve, reopen), backed by the Docs API and the Drive
API's comments endpoints.

## Why a custom server instead of an existing one

Claude Code already ships with a first-party Google Drive connector
(`mcp__claude_ai_Google_Drive__*`), and there's no shortage of third-party
"Google Docs MCP" projects on GitHub/npm. In practice neither covers actual
comment *management*:

- The built-in Drive connector exposes 8 tools total —
  `search_files`, `list_recent_files`, `get_file_metadata`,
  `get_file_permissions`, `read_file_content`, `download_file_content`,
  `create_file`, `copy_file`. Only `read_file_content` touches comments at
  all, via an `includeComments` flag that inlines them as read-only text
  tags in the document body. There's no comment listing with structured IDs
  or resolved status, and no way to create a comment, reply to one, or
  resolve/reopen a thread.
- Third-party servers vary widely in whether they touch comments at all,
  and where they do, comments created through the Drive API generally
  aren't anchored to a text selection in the Docs UI (a Drive API
  limitation this server inherits too — see the note under "Tools exposed"
  below).

This server exists specifically to close that gap: full read/write comment
lifecycle management (list, create, reply, resolve, reopen), not just
read-only visibility into comments that already exist.

## 1. Google Cloud setup (one-time)

1. Create or pick a project at https://console.cloud.google.com/.
2. Enable two APIs for that project:
   - Google Docs API
   - Google Drive API
3. Configure the OAuth consent screen (External is fine; keep it in "Testing"
   mode) and add your own Google account under **Test users**.
4. Create an OAuth client ID: **APIs & Services → Credentials → Create
   Credentials → OAuth client ID → Application type: Desktop app**.
5. Download the client JSON and save it as `credentials.json` in this
   directory (already gitignored).

## 2. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. Authenticate (one-time, interactive)

```bash
.venv/bin/python authenticate.py
```

This opens a browser for Google login/consent and caches a token to
`token.json` (gitignored). Since the OAuth consent screen stays in "Testing"
mode, click through the "unverified app" warning — that's expected for an
app only you use. The MCP server itself never triggers this flow; it only
reads and silently refreshes this cached token. Re-run this script if the
token is ever revoked or deleted.

## 4. Wire it into Claude Code

The server's command always points at wherever *this* repo was cloned — the
venv and `server.py` live here, not in whatever project you happen to be
registering the tool for. Set that path once:

```bash
GDOC_MCP_DIR=/absolute/path/to/gdoc_comment_mcp   # wherever you cloned this repo
```

`PYTHONPATH` must point at `$GDOC_MCP_DIR` — `server.py` is launched directly
(not via `-m`), so without it Python can't find the `gdoc_mcp` package it's
part of, and the server crashes immediately on every connection attempt.

### Local scope (private to you, this project only)

The default for `claude mcp add`. Run from anywhere, including a different
project's directory — only `$GDOC_MCP_DIR` needs to be right, not your `pwd`:

```bash
claude mcp add gdoc-comments -e PYTHONPATH="$GDOC_MCP_DIR" -- "$GDOC_MCP_DIR/.venv/bin/python" "$GDOC_MCP_DIR/gdoc_mcp/server.py"
```

### User scope (private to you, available in every project)

Add `-s user` so the server shows up regardless of which directory you launch
`claude` from — no need to re-register it per project:

```bash
claude mcp add gdoc-comments -s user -e PYTHONPATH="$GDOC_MCP_DIR" -- "$GDOC_MCP_DIR/.venv/bin/python" "$GDOC_MCP_DIR/gdoc_mcp/server.py"
```

### Project scope (shared with anyone who clones a given project)

Add `-s project` while standing inside *that other project's* directory —
this writes a `.mcp.json` there (not in `gdoc_comment_mcp`), which you'd
commit so teammates get the server automatically when they open that project
in Claude Code:

```bash
cd /path/to/some/other/project
claude mcp add gdoc-comments -s project -e PYTHONPATH="$GDOC_MCP_DIR" -- "$GDOC_MCP_DIR/.venv/bin/python" "$GDOC_MCP_DIR/gdoc_mcp/server.py"
```

Each teammate still needs to complete their own [Google Cloud
setup](#1-google-cloud-setup-one-time) and [authenticate](#3-authenticate-one-time-interactive) locally —
`.mcp.json` only wires up the server command, not credentials.

## Tools exposed

- `read_google_doc(document_id)` — title + flattened text content
- `insert_text_in_doc(document_id, index, text)`
- `append_text_to_doc(document_id, text)`
- `replace_text_in_doc(document_id, find_text, replace_text, match_case)`
- `list_doc_comments(document_id, include_resolved)`
- `get_doc_comment(document_id, comment_id)`
- `create_doc_comment(document_id, content, quoted_text)`
- `reply_to_doc_comment(document_id, comment_id, content)`
- `resolve_doc_comment(document_id, comment_id, content)`
- `reopen_doc_comment(document_id, comment_id, content)`

`document_id` accepts either a bare document ID or a full
`https://docs.google.com/document/d/...` URL.

Note: new comments created via the API are not anchored to a specific text
selection — the Drive API doesn't expose that. `quoted_text` is shown as
context alongside the comment but won't highlight a range in the doc.

## Tests

```bash
.venv/bin/python -m pytest tests/
```
