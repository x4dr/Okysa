import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from Golconda import Tools
import time


@pytest.mark.asyncio
async def test_delete_replies(mock_message):
    Tools.sent_messages[mock_message.id] = {
        "received": time.time(),
        "replies": [AsyncMock(), AsyncMock()],
    }
    await Tools.delete_replies(mock_message.id)
    assert mock_message.id not in Tools.sent_messages


def test_extract_comment():
    msg_list, comment = Tools.extract_comment("roll 1d20 // for fun")
    assert " ".join(msg_list).strip() == "roll 1d20"
    assert comment.strip() == "for fun"

    msg_list, comment = Tools.extract_comment("no comment here")
    assert " ".join(msg_list) == "no comment here"
    assert comment == ""


@pytest.mark.asyncio
async def test_split_send(mock_channel):
    lines = ["line1", "line2", "line3"]
    send = mock_channel.send

    await Tools.split_send(send, lines)
    send.assert_called_with("```line1\nline2\nline3\n```")

    many_lines = ["a" * 100] * 30
    await Tools.split_send(send, many_lines)
    assert send.call_count > 1


@pytest.mark.asyncio
async def test_define(mock_message):
    mock_storage = {"defines": {}}

    await Tools.define("A = B", mock_message, mock_storage)
    assert mock_storage["defines"]["A"] == "B"
    mock_message.add_reaction.assert_called_with("👍")

    mock_message.author.send.reset_mock()
    await Tools.define("A", mock_message, mock_storage)
    mock_message.author.send.assert_called_with("B")

    mock_message.author.send.reset_mock()
    await Tools.define("=?", mock_message, mock_storage)
    mock_message.author.send.assert_called()
    args, _ = mock_message.author.send.call_args
    assert "def A = B" in args[0]


@pytest.mark.asyncio
async def test_undefine(mock_message):
    mock_storage = {"defines": {"A": "B", "C": "D"}}
    react = AsyncMock()

    await Tools.undefine("A", react, mock_storage)
    assert "A" not in mock_storage["defines"]
    assert "C" in mock_storage["defines"]
    react.assert_called_with("👍")

    await Tools.undefine("Z", react, mock_storage)
    react.assert_called_with("❓")


def test_who_am_i():
    persist = {"NossiAccount": "User1", "DiscordAccount": "123"}
    mock_storage = MagicMock()

    mock_storage.load_conf.return_value = "123(metadata)"

    user = Tools.who_am_i(persist, mock_storage)
    assert user == "User1"

    mock_storage.load_conf.return_value = "999(metadata)"
    with pytest.raises(Tools.DescriptiveError):
        Tools.who_am_i(persist, mock_storage)


@pytest.mark.asyncio
@patch("Golconda.Tools.who_am_i")
async def test_mutate_message(mock_who):
    mock_who.return_value = "User1"
    storage_mock = MagicMock()
    storage_mock.storage = {"test_mention": {"defines": {"foo": "bar"}}}

    with patch("Golconda.Tools.load_user_char_stats", return_value={}):
        msg, dbg = await Tools.mutate_message(
            "replace foo", storage_mock, "<@test_mention>"
        )
        assert msg == "replace bar"


@pytest.mark.asyncio
async def test_tools_split_send_pagination(mock_channel):
    mock_msg = MagicMock()
    mock_msg.reply = AsyncMock()

    lines = ["Line"] * 50
    await Tools.split_send(mock_msg.reply, lines)
    assert mock_msg.reply.call_count >= 1


def test_tools_mentionreplacer_logic():
    client = MagicMock()
    user_mock = MagicMock()
    user_mock.name = "foo"
    client.get_user.return_value = user_mock

    replacer = Tools.mentionreplacer(client)
    mock_match = MagicMock()
    mock_match.group.return_value = "123"

    res = replacer(mock_match)
    assert res == "@foo"
