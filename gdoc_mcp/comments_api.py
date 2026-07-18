"""Thin wrapper over the Drive API v3 comments/replies endpoints.

Google Docs comments live in the Drive API, not the Docs API. Every function
takes an already-built `service` so this module has no direct auth
dependency and stays easy to unit test with a stub/mock service.

Note: anchoring a new comment to a precise text range uses an undocumented,
Docs-editor-specific `anchor` region format, so it isn't supported here.
`quoted_file_content` is included as best-effort context text shown
alongside the comment.
"""

from googleapiclient.discovery import Resource, build
from google.oauth2.credentials import Credentials

COMMENT_FIELDS = (
    "id,content,author,createdTime,modifiedTime,resolved,quotedFileContent,"
    "replies(id,content,author,createdTime,action)"
)
REPLY_FIELDS = "id,content,author,createdTime,action"


def build_service(creds: Credentials) -> Resource:
    return build("drive", "v3", credentials=creds)


def list_comments(service: Resource, file_id: str, include_resolved: bool = True) -> list:
    comments = []
    page_token = None
    while True:
        response = (
            service.comments()
            .list(
                fileId=file_id,
                fields=f"nextPageToken,comments({COMMENT_FIELDS})",
                pageToken=page_token,
                includeDeleted=False,
            )
            .execute()
        )
        comments.extend(response.get("comments", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    if not include_resolved:
        comments = [c for c in comments if not c.get("resolved")]
    return comments


def get_comment(service: Resource, file_id: str, comment_id: str) -> dict:
    return (
        service.comments()
        .get(fileId=file_id, commentId=comment_id, fields=COMMENT_FIELDS)
        .execute()
    )


def create_comment(
    service: Resource, file_id: str, content: str, quoted_text: str | None = None
) -> dict:
    body = {"content": content}
    if quoted_text:
        body["quotedFileContent"] = {"mimeType": "text/plain", "value": quoted_text}
    return (
        service.comments()
        .create(fileId=file_id, body=body, fields=COMMENT_FIELDS)
        .execute()
    )


def reply_to_comment(service: Resource, file_id: str, comment_id: str, content: str) -> dict:
    body = {"content": content}
    return (
        service.replies()
        .create(fileId=file_id, commentId=comment_id, body=body, fields=REPLY_FIELDS)
        .execute()
    )


def resolve_comment(
    service: Resource, file_id: str, comment_id: str, content: str = "Resolved."
) -> dict:
    body = {"content": content, "action": "resolve"}
    return (
        service.replies()
        .create(fileId=file_id, commentId=comment_id, body=body, fields=REPLY_FIELDS)
        .execute()
    )


def reopen_comment(
    service: Resource, file_id: str, comment_id: str, content: str = "Reopened."
) -> dict:
    body = {"content": content, "action": "reopen"}
    return (
        service.replies()
        .create(fileId=file_id, commentId=comment_id, body=body, fields=REPLY_FIELDS)
        .execute()
    )
