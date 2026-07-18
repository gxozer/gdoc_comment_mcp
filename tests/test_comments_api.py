from unittest.mock import MagicMock

from gdoc_mcp import comments_api


def test_list_comments_paginates_until_no_next_page_token():
    service = MagicMock()
    service.comments.return_value.list.return_value.execute.side_effect = [
        {"comments": [{"id": "c1"}], "nextPageToken": "page2"},
        {"comments": [{"id": "c2"}]},
    ]

    result = comments_api.list_comments(service, "file123")

    assert result == [{"id": "c1"}, {"id": "c2"}]
    assert service.comments.return_value.list.return_value.execute.call_count == 2


def test_list_comments_filters_resolved_when_requested():
    service = MagicMock()
    service.comments.return_value.list.return_value.execute.return_value = {
        "comments": [
            {"id": "c1", "resolved": True},
            {"id": "c2", "resolved": False},
        ]
    }

    result = comments_api.list_comments(service, "file123", include_resolved=False)

    assert result == [{"id": "c2", "resolved": False}]


def test_get_comment_calls_with_expected_args():
    service = MagicMock()
    service.comments.return_value.get.return_value.execute.return_value = {"id": "c1"}

    result = comments_api.get_comment(service, "file123", "c1")

    assert result == {"id": "c1"}
    service.comments.return_value.get.assert_called_once_with(
        fileId="file123", commentId="c1", fields=comments_api.COMMENT_FIELDS
    )


def test_create_comment_without_quoted_text():
    service = MagicMock()
    service.comments.return_value.create.return_value.execute.return_value = {"id": "c1"}

    comments_api.create_comment(service, "file123", "Nice work")

    service.comments.return_value.create.assert_called_once_with(
        fileId="file123",
        body={"content": "Nice work"},
        fields=comments_api.COMMENT_FIELDS,
    )


def test_create_comment_with_quoted_text():
    service = MagicMock()
    service.comments.return_value.create.return_value.execute.return_value = {"id": "c1"}

    comments_api.create_comment(service, "file123", "Fix this", quoted_text="the offending sentence")

    service.comments.return_value.create.assert_called_once_with(
        fileId="file123",
        body={
            "content": "Fix this",
            "quotedFileContent": {"mimeType": "text/plain", "value": "the offending sentence"},
        },
        fields=comments_api.COMMENT_FIELDS,
    )


def test_reply_to_comment():
    service = MagicMock()
    service.replies.return_value.create.return_value.execute.return_value = {"id": "r1"}

    comments_api.reply_to_comment(service, "file123", "c1", "I agree")

    service.replies.return_value.create.assert_called_once_with(
        fileId="file123",
        commentId="c1",
        body={"content": "I agree"},
        fields=comments_api.REPLY_FIELDS,
    )


def test_resolve_comment_sets_resolve_action():
    service = MagicMock()
    service.replies.return_value.create.return_value.execute.return_value = {"id": "r1"}

    comments_api.resolve_comment(service, "file123", "c1", "Fixed, thanks")

    service.replies.return_value.create.assert_called_once_with(
        fileId="file123",
        commentId="c1",
        body={"content": "Fixed, thanks", "action": "resolve"},
        fields=comments_api.REPLY_FIELDS,
    )


def test_reopen_comment_sets_reopen_action():
    service = MagicMock()
    service.replies.return_value.create.return_value.execute.return_value = {"id": "r1"}

    comments_api.reopen_comment(service, "file123", "c1")

    service.replies.return_value.create.assert_called_once_with(
        fileId="file123",
        commentId="c1",
        body={"content": "Reopened.", "action": "reopen"},
        fields=comments_api.REPLY_FIELDS,
    )
