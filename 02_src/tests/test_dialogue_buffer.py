"""Tests for DialogueBuffer."""

from datetime import datetime, timezone

import pytest

from core.dialogue.buffer import DialogueBuffer
from core.models import DialogueState, Message


class TestDialogueBuffer:
    """Tests for DialogueBuffer."""

    def test_add_message(self):
        """Test adding a message to buffer."""
        state = DialogueState(user_id="user1", dialogue_id="dialogue1")
        buffer = DialogueBuffer(state)

        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )

        buffer.add(msg)

        all_messages = buffer.get_all()
        assert len(all_messages) == 1
        assert all_messages[0].content == "Hello"

    def test_add_multiple_messages(self):
        """Test adding multiple messages to buffer."""
        state = DialogueState(user_id="user1", dialogue_id="dialogue1")
        buffer = DialogueBuffer(state)

        ts = datetime.now(timezone.utc)
        msg1 = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="First",
            timestamp=ts,
        )
        msg2 = Message(
            id="msg2",
            dialogue_id="dialogue1",
            role="assistant",
            content="Second",
            timestamp=ts,
        )

        buffer.add(msg1)
        buffer.add(msg2)

        all_messages = buffer.get_all()
        assert len(all_messages) == 2

    def test_get_unpublished_no_timestamp(self):
        """Test get_unpublished when last_published_timestamp is None."""
        state = DialogueState(
            user_id="user1", dialogue_id="dialogue1", last_published_timestamp=None
        )
        buffer = DialogueBuffer(state)

        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )

        buffer.add(msg)
        unpublished = buffer.get_unpublished()

        assert len(unpublished) == 1
        assert unpublished[0].content == "Hello"

    def test_get_unpublished_after_timestamp(self):
        """Test get_unpublished filters by last_published_timestamp."""
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
        ts3 = datetime(2024, 1, 1, 12, 10, 0, tzinfo=timezone.utc)

        state = DialogueState(
            user_id="user1",
            dialogue_id="dialogue1",
            last_published_timestamp=ts2,
        )
        buffer = DialogueBuffer(state)

        msg1 = Message(
            id="msg1", dialogue_id="dialogue1", role="user", content="Before", timestamp=ts1
        )
        msg2 = Message(
            id="msg2", dialogue_id="dialogue1", role="user", content="At", timestamp=ts2
        )
        msg3 = Message(
            id="msg3", dialogue_id="dialogue1", role="user", content="After", timestamp=ts3
        )

        buffer.add(msg1)
        buffer.add(msg2)
        buffer.add(msg3)

        unpublished = buffer.get_unpublished()

        # Should only include messages after ts2
        assert len(unpublished) == 1
        assert unpublished[0].content == "After"

    def test_get_unpublished_returns_empty(self):
        """Test get_unpublished when no new messages."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        state = DialogueState(
            user_id="user1", dialogue_id="dialogue1", last_published_timestamp=ts
        )
        buffer = DialogueBuffer(state)

        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Before",
            timestamp=ts,
        )

        buffer.add(msg)
        unpublished = buffer.get_unpublished()

        assert len(unpublished) == 0

    def test_get_all_returns_all_messages(self):
        """Test that get_all returns all messages regardless of timestamp."""
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

        state = DialogueState(
            user_id="user1",
            dialogue_id="dialogue1",
            last_published_timestamp=ts2,
        )
        buffer = DialogueBuffer(state)

        msg1 = Message(
            id="msg1", dialogue_id="dialogue1", role="user", content="First", timestamp=ts1
        )
        msg2 = Message(
            id="msg2", dialogue_id="dialogue1", role="user", content="Second", timestamp=ts2
        )

        buffer.add(msg1)
        buffer.add(msg2)

        all_messages = buffer.get_all()
        assert len(all_messages) == 2

    def test_clear(self):
        """Test clearing the buffer."""
        state = DialogueState(user_id="user1", dialogue_id="dialogue1")
        buffer = DialogueBuffer(state)

        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )

        buffer.add(msg)
        assert len(buffer.get_all()) == 1

        buffer.clear()
        assert len(buffer.get_all()) == 0

    def test_set_published_timestamp(self):
        """Test updating last_published_timestamp."""
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

        state = DialogueState(
            user_id="user1",
            dialogue_id="dialogue1",
            last_published_timestamp=ts1,
        )
        buffer = DialogueBuffer(state)

        buffer.set_published_timestamp(ts2)

        # After updating, get_unpublished should filter from ts2
        msg = Message(
            id="msg1", dialogue_id="dialogue1", role="user", content="Test", timestamp=ts1
        )
        buffer.add(msg)

        unpublished = buffer.get_unpublished()
        assert len(unpublished) == 0
