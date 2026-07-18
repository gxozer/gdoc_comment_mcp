"""MCP server exposing Google Docs content + comment operations as tools."""

import re

from mcp.server.fastmcp import FastMCP

from gdoc_mcp import auth, comments_api, docs_api

mcp = FastMCP("gdoc-comments")

_DOC_URL_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def _resolve_document_id(document_id_or_url: str) -> str:
    """Accepts either a bare document ID or a full Google Docs URL."""
    match = _DOC_URL_RE.search(document_id_or_url)
    return match.group(1) if match else document_id_or_url


def _docs_service():
    return docs_api.build_service(auth.get_credentials())


def _drive_service():
    return comments_api.build_service(auth.get_credentials())


@mcp.tool()
def read_google_doc(document_id: str) -> dict:
    """Read a Google Doc's title and full text content.

    document_id: the document ID, or a full https://docs.google.com/document/d/... URL.
    """
    doc_id = _resolve_document_id(document_id)
    return docs_api.read_document(_docs_service(), doc_id)


@mcp.tool()
def insert_text_in_doc(document_id: str, index: int, text: str) -> dict:
    """Insert text into a Google Doc at a specific character index.

    Use read_google_doc first if you need to figure out an index; for simply
    adding text to the end of the doc, prefer append_text_to_doc instead.
    """
    doc_id = _resolve_document_id(document_id)
    docs_api.insert_text(_docs_service(), doc_id, index, text)
    return {"status": "ok", "document_id": doc_id}


@mcp.tool()
def append_text_to_doc(document_id: str, text: str) -> dict:
    """Append text to the end of a Google Doc."""
    doc_id = _resolve_document_id(document_id)
    docs_api.append_text(_docs_service(), doc_id, text)
    return {"status": "ok", "document_id": doc_id}


@mcp.tool()
def replace_text_in_doc(
    document_id: str, find_text: str, replace_text: str, match_case: bool = True
) -> dict:
    """Find and replace every occurrence of a string in a Google Doc."""
    doc_id = _resolve_document_id(document_id)
    docs_api.replace_text(_docs_service(), doc_id, find_text, replace_text, match_case)
    return {"status": "ok", "document_id": doc_id}


@mcp.tool()
def list_doc_comments(document_id: str, include_resolved: bool = True) -> list:
    """List all comments (with their replies) on a Google Doc."""
    doc_id = _resolve_document_id(document_id)
    return comments_api.list_comments(_drive_service(), doc_id, include_resolved)


@mcp.tool()
def get_doc_comment(document_id: str, comment_id: str) -> dict:
    """Fetch a single comment (with replies) by ID."""
    doc_id = _resolve_document_id(document_id)
    return comments_api.get_comment(_drive_service(), doc_id, comment_id)


@mcp.tool()
def create_doc_comment(document_id: str, content: str, quoted_text: str = "") -> dict:
    """Create a new top-level comment on a Google Doc.

    quoted_text, if given, is shown as context text alongside the comment but
    does not anchor it to a precise selection in the document (the Drive API
    does not expose that capability).
    """
    doc_id = _resolve_document_id(document_id)
    return comments_api.create_comment(_drive_service(), doc_id, content, quoted_text or None)


@mcp.tool()
def reply_to_doc_comment(document_id: str, comment_id: str, content: str) -> dict:
    """Reply to an existing comment thread."""
    doc_id = _resolve_document_id(document_id)
    return comments_api.reply_to_comment(_drive_service(), doc_id, comment_id, content)


@mcp.tool()
def resolve_doc_comment(document_id: str, comment_id: str, content: str = "Resolved.") -> dict:
    """Resolve a comment thread, optionally with a closing reply message."""
    doc_id = _resolve_document_id(document_id)
    return comments_api.resolve_comment(_drive_service(), doc_id, comment_id, content)


@mcp.tool()
def reopen_doc_comment(document_id: str, comment_id: str, content: str = "Reopened.") -> dict:
    """Reopen a previously resolved comment thread."""
    doc_id = _resolve_document_id(document_id)
    return comments_api.reopen_comment(_drive_service(), doc_id, comment_id, content)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
