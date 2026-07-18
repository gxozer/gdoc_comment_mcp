from unittest.mock import MagicMock

from gdoc_mcp import docs_api


def make_service(get_return=None, batch_return=None):
    service = MagicMock()
    service.documents.return_value.get.return_value.execute.return_value = get_return
    service.documents.return_value.batchUpdate.return_value.execute.return_value = batch_return
    return service


def paragraph(text, style="NORMAL_TEXT", bullet=False):
    element = {
        "paragraph": {
            "elements": [{"textRun": {"content": text}}],
            "paragraphStyle": {"namedStyleType": style},
        }
    }
    if bullet:
        element["paragraph"]["bullet"] = {"listId": "abc"}
    return element


def test_extract_text_plain_paragraph():
    document = {"body": {"content": [paragraph("Hello world\n")]}}
    assert docs_api.extract_text(document) == "Hello world"


def test_extract_text_heading_gets_markdown_prefix():
    document = {"body": {"content": [paragraph("Section One\n", style="HEADING_2")]}}
    assert docs_api.extract_text(document) == "## Section One"


def test_extract_text_bullet_gets_dash_prefix():
    document = {"body": {"content": [paragraph("Item one\n", bullet=True)]}}
    assert docs_api.extract_text(document) == "- Item one"


def test_extract_text_title_style():
    document = {"body": {"content": [paragraph("My Doc\n", style="TITLE")]}}
    assert docs_api.extract_text(document) == "# My Doc"


def test_extract_text_table():
    table_element = {
        "table": {
            "tableRows": [
                {
                    "tableCells": [
                        {"content": [{"paragraph": {"elements": [{"textRun": {"content": "A"}}]}}]},
                        {"content": [{"paragraph": {"elements": [{"textRun": {"content": "B"}}]}}]},
                    ]
                }
            ]
        }
    }
    document = {"body": {"content": [table_element]}}
    assert docs_api.extract_text(document) == "A | B"


def test_extract_text_multiple_lines():
    document = {
        "body": {
            "content": [
                paragraph("Title\n", style="TITLE"),
                paragraph("Intro paragraph.\n"),
                paragraph("First bullet\n", bullet=True),
            ]
        }
    }
    assert docs_api.extract_text(document) == "# Title\nIntro paragraph.\n- First bullet"


def test_read_document_returns_title_and_text():
    doc = {
        "title": "My Document",
        "body": {"content": [paragraph("Hello\n")]},
    }
    service = make_service(get_return=doc)

    result = docs_api.read_document(service, "doc123")

    assert result == {"document_id": "doc123", "title": "My Document", "text": "Hello"}
    service.documents.return_value.get.assert_called_once_with(documentId="doc123")


def test_insert_text_sends_correct_request():
    service = make_service(batch_return={"documentId": "doc123"})

    docs_api.insert_text(service, "doc123", 5, "hi")

    service.documents.return_value.batchUpdate.assert_called_once_with(
        documentId="doc123",
        body={"requests": [{"insertText": {"location": {"index": 5}, "text": "hi"}}]},
    )


def test_append_text_uses_body_end_index_minus_one():
    doc = {"body": {"content": [{"endIndex": 42, "paragraph": {"elements": []}}]}}
    service = make_service(get_return=doc, batch_return={})

    docs_api.append_text(service, "doc123", "the end")

    service.documents.return_value.batchUpdate.assert_called_once_with(
        documentId="doc123",
        body={"requests": [{"insertText": {"location": {"index": 41}, "text": "the end"}}]},
    )


def test_replace_text_sends_correct_request():
    service = make_service(batch_return={})

    docs_api.replace_text(service, "doc123", "foo", "bar", match_case=False)

    service.documents.return_value.batchUpdate.assert_called_once_with(
        documentId="doc123",
        body={
            "requests": [
                {
                    "replaceAllText": {
                        "containsText": {"text": "foo", "matchCase": False},
                        "replaceText": "bar",
                    }
                }
            ]
        },
    )
