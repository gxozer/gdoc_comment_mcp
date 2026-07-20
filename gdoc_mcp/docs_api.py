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


def _iter_text_runs(document: dict):
    """Yields (start_index, content) for every textRun in document order,
    descending into table cells. Indices are the real Docs API positions
    carried on each element, not recomputed offsets.
    """

    def walk(content_list):
        for element in content_list:
            paragraph = element.get("paragraph")
            if paragraph is not None:
                for el in paragraph.get("elements", []):
                    run = el.get("textRun")
                    if run is not None:
                        yield el["startIndex"], run.get("content", "")
                continue
            table = element.get("table")
            if table is not None:
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        yield from walk(cell.get("content", []))

    yield from walk(document.get("body", {}).get("content", []))


def find_text_ranges(document: dict, target: str) -> list:
    """Returns [(start_index, end_index), ...] for every occurrence of `target`
    that falls entirely within a single textRun. A match split across
    differently-styled runs (e.g. partly bold) will not be found — a known
    limitation, acceptable for the plain-prose reference text this targets.
    """
    ranges = []
    for start_index, content in _iter_text_runs(document):
        offset = 0
        while True:
            pos = content.find(target, offset)
            if pos == -1:
                break
            ranges.append((start_index + pos, start_index + pos + len(target)))
            offset = pos + 1
    return ranges


def _set_link_request(start_index: int, end_index: int, url: str) -> dict:
    return {
        "updateTextStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "textStyle": {"link": {"url": url}},
            "fields": "link",
        }
    }


def linkify_text(service: Resource, document_id: str, display_text: str, url: str) -> int:
    """Turns every existing bare occurrence of `display_text` into a real
    hyperlink pointing at `url`, without changing the visible text. Returns
    the number of occurrences linked.
    """
    document = service.documents().get(documentId=document_id).execute()
    ranges = find_text_ranges(document, display_text)
    if not ranges:
        return 0
    requests = [_set_link_request(start, end, url) for start, end in ranges]
    service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return len(ranges)


def replace_url_suffix_with_link(
    service: Resource, document_id: str, display_text: str, url: str
) -> int:
    """Finds every occurrence of the literal pattern "{display_text} ({url})"
    (the plain-text 'ugly annotation' form left by an earlier workaround),
    replaces it with just `display_text`, and makes that text a real
    hyperlink to `url`. Returns the number of occurrences fixed.

    Occurrences are processed in descending index order within the batch so
    that shrinking an earlier-in-document occurrence never invalidates the
    still-pending, higher-index occurrences' precomputed ranges.
    """
    ugly = f"{display_text} ({url})"
    document = service.documents().get(documentId=document_id).execute()
    ranges = sorted(find_text_ranges(document, ugly), key=lambda r: r[0], reverse=True)
    if not ranges:
        return 0

    requests = []
    for start, end in ranges:
        requests.append({"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}})
        requests.append({"insertText": {"location": {"index": start}, "text": display_text}})
        requests.append(_set_link_request(start, start + len(display_text), url))

    service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return len(ranges)
