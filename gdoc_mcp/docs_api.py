"""Thin wrapper over the Google Docs API v1: reading and editing document content.

Every function takes an already-built `service` (googleapiclient Resource) so
the module has no direct dependency on auth and stays easy to unit test with
a stub/mock service.
"""

from googleapiclient.discovery import Resource, build
from google.oauth2.credentials import Credentials


def build_service(creds: Credentials) -> Resource:
    return build("docs", "v1", credentials=creds)


def _extract_paragraph_text(paragraph: dict) -> str:
    return "".join(
        el.get("textRun", {}).get("content", "") for el in paragraph.get("elements", [])
    )


def _extract_table_text(table: dict) -> str:
    rows = []
    for row in table.get("tableRows", []):
        cells = []
        for cell in row.get("tableCells", []):
            cell_text = "".join(
                _extract_paragraph_text(content["paragraph"])
                for content in cell.get("content", [])
                if "paragraph" in content
            )
            cells.append(cell_text.strip())
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def extract_text(document: dict) -> str:
    """Flattens a Docs API document resource into readable plain text.

    Headings are prefixed with markdown-style '#'s and bullet items with '-'
    so structure survives the flattening without needing the full JSON.
    """
    lines = []
    for element in document.get("body", {}).get("content", []):
        if "table" in element:
            lines.append(_extract_table_text(element["table"]))
            continue

        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        text = _extract_paragraph_text(paragraph).rstrip("\n")
        style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")

        if paragraph.get("bullet"):
            text = f"- {text}"
        elif style.startswith("HEADING_"):
            level = style.rsplit("_", 1)[-1]
            prefix = "#" * int(level) if level.isdigit() else "#"
            text = f"{prefix} {text}"
        elif style in ("TITLE", "SUBTITLE"):
            text = f"# {text}"

        lines.append(text)
    return "\n".join(lines)


def read_document(service: Resource, document_id: str) -> dict:
    document = service.documents().get(documentId=document_id).execute()
    return {
        "document_id": document_id,
        "title": document.get("title", ""),
        "text": extract_text(document),
    }


def insert_text(service: Resource, document_id: str, index: int, text: str) -> dict:
    requests = [{"insertText": {"location": {"index": index}, "text": text}}]
    return service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()


def append_text(service: Resource, document_id: str, text: str) -> dict:
    document = service.documents().get(documentId=document_id).execute()
    end_index = document["body"]["content"][-1]["endIndex"] - 1
    return insert_text(service, document_id, end_index, text)


def replace_text(
    service: Resource,
    document_id: str,
    find_text: str,
    replace_with: str,
    match_case: bool = True,
) -> dict:
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": find_text, "matchCase": match_case},
                "replaceText": replace_with,
            }
        }
    ]
    return service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()
