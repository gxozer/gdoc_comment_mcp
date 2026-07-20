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


def indexed_paragraph(text, start_index):
    """Paragraph helper carrying a real startIndex on its textRun element,
    needed for range-finding tests (unlike `paragraph()` above, which omits
    it since extract_text doesn't need it)."""
    return {
        "paragraph": {
            "elements": [
                {
                    "startIndex": start_index,
                    "endIndex": start_index + len(text),
                    "textRun": {"content": text},
                }
            ],
        }
    }


def test_find_text_ranges_single_run():
    document = {"body": {"content": [indexed_paragraph("Hello world\n", start_index=1)]}}
    assert docs_api.find_text_ranges(document, "world") == [(7, 12)]


def test_find_text_ranges_multiple_occurrences_same_run():
    document = {"body": {"content": [indexed_paragraph("foo foo foo\n", start_index=1)]}}
    assert docs_api.find_text_ranges(document, "foo") == [(1, 4), (5, 8), (9, 12)]


def test_find_text_ranges_across_paragraphs():
    document = {
        "body": {
            "content": [
                indexed_paragraph("first line\n", start_index=1),
                indexed_paragraph("second target line\n", start_index=12),
            ]
        }
    }
    assert docs_api.find_text_ranges(document, "target") == [(19, 25)]


def test_find_text_ranges_in_table_cell():
    document = {
        "body": {
            "content": [
                {
                    "table": {
                        "tableRows": [
                            {
                                "tableCells": [
                                    {
                                        "content": [
                                            indexed_paragraph("cell target text\n", start_index=5)
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
    }
    assert docs_api.find_text_ranges(document, "target") == [(10, 16)]


def test_find_text_ranges_no_match_returns_empty():
    document = {"body": {"content": [indexed_paragraph("Hello world\n", start_index=1)]}}
    assert docs_api.find_text_ranges(document, "missing") == []


def test_linkify_text_sends_update_text_style_per_occurrence():
    doc = {"body": {"content": [indexed_paragraph("see foo and foo\n", start_index=1)]}}
    service = make_service(get_return=doc, batch_return={})

    count = docs_api.linkify_text(service, "doc123", "foo", "https://example.com")

    assert count == 2
    service.documents.return_value.batchUpdate.assert_called_once_with(
        documentId="doc123",
        body={
            "requests": [
                {
                    "updateTextStyle": {
                        "range": {"startIndex": 5, "endIndex": 8},
                        "textStyle": {"link": {"url": "https://example.com"}},
                        "fields": "link",
                    }
                },
                {
                    "updateTextStyle": {
                        "range": {"startIndex": 13, "endIndex": 16},
                        "textStyle": {"link": {"url": "https://example.com"}},
                        "fields": "link",
                    }
                },
            ]
        },
    )


def test_linkify_text_no_match_skips_batch_update():
    doc = {"body": {"content": [indexed_paragraph("Hello world\n", start_index=1)]}}
    service = make_service(get_return=doc, batch_return={})

    count = docs_api.linkify_text(service, "doc123", "missing", "https://example.com")

    assert count == 0
    service.documents.return_value.batchUpdate.assert_not_called()


def test_replace_url_suffix_with_link_single_occurrence():
    text = "See foo.md (https://example.com/doc) for details\n"
    doc = {"body": {"content": [indexed_paragraph(text, start_index=1)]}}
    service = make_service(get_return=doc, batch_return={})

    count = docs_api.replace_url_suffix_with_link(
        service, "doc123", "foo.md", "https://example.com/doc"
    )

    assert count == 1
    ugly = "foo.md (https://example.com/doc)"
    start = 1 + text.index(ugly)
    end = start + len(ugly)
    service.documents.return_value.batchUpdate.assert_called_once_with(
        documentId="doc123",
        body={
            "requests": [
                {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}},
                {"insertText": {"location": {"index": start}, "text": "foo.md"}},
                {
                    "updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": start + len("foo.md")},
                        "textStyle": {"link": {"url": "https://example.com/doc"}},
                        "fields": "link",
                    }
                },
            ]
        },
    )


def test_replace_url_suffix_with_link_multiple_occurrences_processed_in_reverse():
    text = "foo.md (https://x) and later foo.md (https://x)\n"
    doc = {"body": {"content": [indexed_paragraph(text, start_index=1)]}}
    service = make_service(get_return=doc, batch_return={})

    count = docs_api.replace_url_suffix_with_link(service, "doc123", "foo.md", "https://x")

    assert count == 2
    requests = service.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    first_delete = requests[0]["deleteContentRange"]["range"]
    second_delete = requests[3]["deleteContentRange"]["range"]
    # the later (higher-index) occurrence must be processed first, so
    # deleting/inserting for it doesn't shift the still-pending occurrence's indices
    assert first_delete["startIndex"] > second_delete["startIndex"]


def test_replace_url_suffix_with_link_no_match_skips_batch_update():
    doc = {"body": {"content": [indexed_paragraph("nothing here\n", start_index=1)]}}
    service = make_service(get_return=doc, batch_return={})

    count = docs_api.replace_url_suffix_with_link(service, "doc123", "foo.md", "https://x")

    assert count == 0
    service.documents.return_value.batchUpdate.assert_not_called()
