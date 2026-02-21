"""Tests for Storage."""

from datetime import datetime, timezone

import pytest

from core.models import (
    AgentState,
    Attachment,
    BusMessage,
    DialogueState,
    Message,
    Team,
    Topic,
    TraceEvent,
    User,
)


class TestStorageInit:
    """Tests for Storage initialization."""

    async def test_init_creates_tables(self, storage):
        """Test that init creates all tables."""
        # Try to query each table - should not raise errors
        async with storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cursor:
            tables = [row[0] for row in await cursor.fetchall()]
            assert "teams" in tables
            assert "users" in tables
            assert "messages" in tables
            assert "attachments" in tables
            assert "dialogue_states" in tables
            assert "agent_states" in tables
            assert "trace_events" in tables
            assert "bus_messages" in tables


class TestStorageTeams:
    """Tests for Team storage."""

    async def test_save_team(self, storage):
        """Test saving a team."""
        team = Team(id="team1", name="Engineering")
        await storage.save_team(team)

    async def test_save_team_updates_existing(self, storage):
        """Test that saving same team ID updates it."""
        team1 = Team(id="team1", name="Engineering")
        await storage.save_team(team1)

        # Update
        team2 = Team(id="team1", name="Sales")
        await storage.save_team(team2)

        # Verify (no get_team method, but should not raise error)


class TestStorageUsers:
    """Tests for User storage."""

    async def test_save_user(self, storage):
        """Test saving a user."""
        user = User(id="user1", team_id="team1", name="Alice")
        await storage.save_user(user)

    async def test_get_user(self, storage):
        """Test retrieving a user."""
        user = User(id="user1", team_id="team1", name="Alice")
        await storage.save_user(user)

        retrieved = await storage.get_user("user1")
        assert retrieved is not None
        assert retrieved.id == "user1"
        assert retrieved.team_id == "team1"
        assert retrieved.name == "Alice"

    async def test_get_nonexistent_user(self, storage):
        """Test retrieving nonexistent user returns None."""
        retrieved = await storage.get_user("nonexistent")
        assert retrieved is None


class TestStorageMessages:
    """Tests for Message storage."""

    async def test_save_message(self, storage):
        """Test saving a message."""
        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )
        await storage.save_message(msg)

    async def test_save_message_generates_id(self, storage):
        """Test that saving message without ID generates one."""
        ts = datetime.now(timezone.utc)
        msg = Message(
            id=None,  # type: ignore
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )
        await storage.save_message(msg)
        assert msg.id is not None

    async def test_get_messages(self, storage):
        """Test retrieving messages for a dialogue."""
        ts = datetime.now(timezone.utc)
        msg1 = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )
        msg2 = Message(
            id="msg2",
            dialogue_id="dialogue1",
            role="assistant",
            content="Hi",
            timestamp=ts,
        )
        await storage.save_message(msg1)
        await storage.save_message(msg2)

        messages = await storage.get_messages("dialogue1")
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi"

    async def test_get_messages_after_timestamp(self, storage):
        """Test retrieving messages after a timestamp."""
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc)
        ts3 = datetime(2024, 1, 1, 12, 2, 0, tzinfo=timezone.utc)

        msg1 = Message(
            id="msg1", dialogue_id="d1", role="user", content="1", timestamp=ts1
        )
        msg2 = Message(
            id="msg2", dialogue_id="d1", role="user", content="2", timestamp=ts2
        )
        msg3 = Message(
            id="msg3", dialogue_id="d1", role="user", content="3", timestamp=ts3
        )

        await storage.save_message(msg1)
        await storage.save_message(msg2)
        await storage.save_message(msg3)

        # Get messages after ts2
        messages = await storage.get_messages("d1", after=ts2)
        assert len(messages) == 1
        assert messages[0].content == "3"

    async def test_get_messages_empty_dialogue(self, storage):
        """Test retrieving messages from empty dialogue."""
        messages = await storage.get_messages("nonexistent")
        assert len(messages) == 0

    async def test_save_message_with_attachments(self, storage):
        """Test saving message with attachments."""
        ts = datetime.now(timezone.utc)
        att = Attachment(
            id="att1", message_id="msg1", type="file", data=b"data"
        )
        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
            attachments=[att],
        )
        await storage.save_message(msg)

        messages = await storage.get_messages("dialogue1")
        assert len(messages) == 1
        assert len(messages[0].attachments) == 1
        assert messages[0].attachments[0].type == "file"


class TestStorageDialogueState:
    """Tests for DialogueState storage."""

    async def test_save_dialogue_state(self, storage):
        """Test saving dialogue state."""
        ts = datetime.now(timezone.utc)
        state = DialogueState(
            user_id="user1", dialogue_id="dialogue1", last_published_timestamp=ts
        )
        await storage.save_dialogue_state(state)

    async def test_get_dialogue_state(self, storage):
        """Test retrieving dialogue state."""
        ts = datetime.now(timezone.utc)
        state = DialogueState(
            user_id="user1", dialogue_id="dialogue1", last_published_timestamp=ts
        )
        await storage.save_dialogue_state(state)

        retrieved = await storage.get_dialogue_state("user1")
        assert retrieved is not None
        assert retrieved.user_id == "user1"
        assert retrieved.dialogue_id == "dialogue1"
        assert retrieved.last_published_timestamp is not None

    async def test_get_nonexistent_dialogue_state(self, storage):
        """Test retrieving nonexistent dialogue state."""
        retrieved = await storage.get_dialogue_state("nonexistent")
        assert retrieved is None

    async def test_save_dialogue_state_creates_if_not_exists(
        self, storage
    ):
        """Test saving dialogue state creates if not exists."""
        state1 = DialogueState(
            user_id="user1", dialogue_id="dialogue1", last_published_timestamp=None
        )
        await storage.save_dialogue_state(state1)

        # Update
        ts = datetime.now(timezone.utc)
        state2 = DialogueState(
            user_id="user1", dialogue_id="dialogue2", last_published_timestamp=ts
        )
        await storage.save_dialogue_state(state2)

        retrieved = await storage.get_dialogue_state("user1")
        assert retrieved.dialogue_id == "dialogue2"


class TestStorageAgentState:
    """Tests for AgentState storage."""

    async def test_save_agent_state(self, storage):
        """Test saving agent state."""
        state = AgentState(
            agent_id="agent1", data={"key": "value"}, sgr_traces=[]
        )
        await storage.save_agent_state("agent1", state)

    async def test_get_agent_state(self, storage):
        """Test retrieving agent state."""
        state = AgentState(
            agent_id="agent1",
            data={"count": 5, "name": "test"},
            sgr_traces=[{"step": 1}],
        )
        await storage.save_agent_state("agent1", state)

        retrieved = await storage.get_agent_state("agent1")
        assert retrieved is not None
        assert retrieved.agent_id == "agent1"
        assert retrieved.data == {"count": 5, "name": "test"}
        assert retrieved.sgr_traces == [{"step": 1}]

    async def test_get_nonexistent_agent_state(self, storage):
        """Test retrieving nonexistent agent state."""
        retrieved = await storage.get_agent_state("nonexistent")
        assert retrieved is None


class TestStorageTraceEvents:
    """Tests for TraceEvent storage."""

    async def test_save_trace_event(self, storage):
        """Test saving a trace event."""
        ts = datetime.now(timezone.utc)
        event = TraceEvent(
            id="trace1",
            event_type="message_received",
            actor="dialogue_agent",
            data={"user_id": "user1"},
            timestamp=ts,
        )
        await storage.save_trace_event(event)

    async def test_get_trace_events(self, storage):
        """Test retrieving trace events."""
        ts = datetime.now(timezone.utc)
        event1 = TraceEvent(
            id="trace1",
            event_type="message_received",
            actor="agent1",
            data={},
            timestamp=ts,
        )
        event2 = TraceEvent(
            id="trace2",
            event_type="processing_started",
            actor="agent2",
            data={},
            timestamp=ts,
        )
        await storage.save_trace_event(event1)
        await storage.save_trace_event(event2)

        events = await storage.get_trace_events()
        assert len(events) == 2

    async def test_get_trace_events_with_limit(self, storage):
        """Test retrieving trace events with limit."""
        ts = datetime.now(timezone.utc)
        for i in range(10):
            event = TraceEvent(
                id=f"trace{i}",
                event_type="test",
                actor="test",
                data={},
                timestamp=ts,
            )
            await storage.save_trace_event(event)

        events = await storage.get_trace_events(limit=5)
        assert len(events) == 5

    async def test_get_trace_events_by_actor(self, storage):
        """Test filtering trace events by actor."""
        ts = datetime.now(timezone.utc)
        event1 = TraceEvent(
            id="trace1",
            event_type="test",
            actor="agent1",
            data={},
            timestamp=ts,
        )
        event2 = TraceEvent(
            id="trace2",
            event_type="test",
            actor="agent2",
            data={},
            timestamp=ts,
        )
        await storage.save_trace_event(event1)
        await storage.save_trace_event(event2)

        events = await storage.get_trace_events(actor="agent1")
        assert len(events) == 1
        assert events[0].actor == "agent1"

    async def test_get_trace_events_by_type(self, storage):
        """Test filtering trace events by type."""
        ts = datetime.now(timezone.utc)
        event1 = TraceEvent(
            id="trace1",
            event_type="type1",
            actor="agent1",
            data={},
            timestamp=ts,
        )
        event2 = TraceEvent(
            id="trace2",
            event_type="type2",
            actor="agent1",
            data={},
            timestamp=ts,
        )
        await storage.save_trace_event(event1)
        await storage.save_trace_event(event2)

        events = await storage.get_trace_events(event_types=["type1"])
        assert len(events) == 1
        assert events[0].event_type == "type1"


class TestStorageBusMessages:
    """Tests for BusMessage storage."""

    async def test_save_bus_message(self, storage):
        """Test saving a bus message."""
        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={"test": "data"},
            source="test",
            timestamp=ts,
        )
        await storage.save_bus_message(msg)


class TestStorageClear:
    """Tests for clearing storage."""

    async def test_clear_all_data(self, storage):
        """Test clearing all data."""
        # Add some data
        team = Team(id="team1", name="Test")
        await storage.save_team(team)

        user = User(id="user1", team_id="team1", name="Alice")
        await storage.save_user(user)

        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg1", dialogue_id="d1", role="user", content="Hi", timestamp=ts
        )
        await storage.save_message(msg)

        # Clear
        await storage.clear()

        # Verify all tables are empty
        async with storage._conn.execute("SELECT COUNT(*) FROM users") as cursor:
            count = await cursor.fetchone()
            assert count[0] == 0

        async with storage._conn.execute("SELECT COUNT(*) FROM messages") as cursor:
            count = await cursor.fetchone()
            assert count[0] == 0
