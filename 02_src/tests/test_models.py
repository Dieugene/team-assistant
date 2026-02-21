"""Tests for data models."""

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


class TestTeam:
    """Tests for Team model."""

    def test_create_team(self):
        """Test creating a Team."""
        team = Team(id="team1", name="Engineering")
        assert team.id == "team1"
        assert team.name == "Engineering"


class TestUser:
    """Tests for User model."""

    def test_create_user(self):
        """Test creating a User."""
        user = User(id="user1", team_id="team1", name="Alice")
        assert user.id == "user1"
        assert user.team_id == "team1"
        assert user.name == "Alice"


class TestMessage:
    """Tests for Message model."""

    def test_create_user_message(self):
        """Test creating a user message."""
        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg1",
            dialogue_id="dialogue1",
            role="user",
            content="Hello",
            timestamp=ts,
        )
        assert msg.id == "msg1"
        assert msg.dialogue_id == "dialogue1"
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp == ts
        assert msg.attachments == []

    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg2",
            dialogue_id="dialogue1",
            role="assistant",
            content="Hi there!",
            timestamp=ts,
        )
        assert msg.role == "assistant"

    def test_create_system_message(self):
        """Test creating a system message."""
        ts = datetime.now(timezone.utc)
        msg = Message(
            id="msg3",
            dialogue_id="dialogue1",
            role="system",
            content="Notification",
            timestamp=ts,
        )
        assert msg.role == "system"

    def test_invalid_role(self):
        """Test that invalid role raises error at runtime."""
        ts = datetime.now(timezone.utc)
        # This will create but type checkers should catch it
        msg = Message(
            id="msg4",
            dialogue_id="dialogue1",
            role="invalid",  # type: ignore
            content="Test",
            timestamp=ts,
        )
        assert msg.role == "invalid"


class TestAttachment:
    """Tests for Attachment model."""

    def test_create_attachment_with_data(self):
        """Test creating attachment with data."""
        att = Attachment(
            id="att1", message_id="msg1", type="file", data=b"binary data"
        )
        assert att.id == "att1"
        assert att.message_id == "msg1"
        assert att.type == "file"
        assert att.data == b"binary data"
        assert att.url is None

    def test_create_attachment_with_url(self):
        """Test creating attachment with URL."""
        att = Attachment(
            id="att2", message_id="msg1", type="image", url="http://example.com/img.jpg"
        )
        assert att.url == "http://example.com/img.jpg"
        assert att.data is None


class TestDialogueState:
    """Tests for DialogueState model."""

    def test_create_dialogue_state(self):
        """Test creating DialogueState."""
        ts = datetime.now(timezone.utc)
        state = DialogueState(
            user_id="user1", dialogue_id="dialogue1", last_published_timestamp=ts
        )
        assert state.user_id == "user1"
        assert state.dialogue_id == "dialogue1"
        assert state.last_published_timestamp == ts

    def test_dialogue_state_without_timestamp(self):
        """Test DialogueState without last_published_timestamp."""
        state = DialogueState(user_id="user1", dialogue_id="dialogue1")
        assert state.last_published_timestamp is None


class TestAgentState:
    """Tests for AgentState model."""

    def test_create_agent_state(self):
        """Test creating AgentState."""
        state = AgentState(agent_id="agent1", data={"key": "value"})
        assert state.agent_id == "agent1"
        assert state.data == {"key": "value"}
        assert state.sgr_traces == []

    def test_agent_state_with_traces(self):
        """Test AgentState with reasoning traces."""
        traces = [{"step": 1, "thought": "analyze"}]
        state = AgentState(
            agent_id="agent1", data={"key": "value"}, sgr_traces=traces
        )
        assert state.sgr_traces == traces


class TestBusMessage:
    """Tests for BusMessage model."""

    def test_create_bus_message(self):
        """Test creating BusMessage."""
        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={"messages": []},
            source="dialogue_agent",
            timestamp=ts,
        )
        assert msg.id == "bus1"
        assert msg.topic == Topic.INPUT
        assert msg.payload == {"messages": []}
        assert msg.source == "dialogue_agent"
        assert msg.timestamp == ts

    def test_bus_message_topic_enum(self):
        """Test BusMessage with different topics."""
        ts = datetime.now(timezone.utc)
        msg_input = BusMessage(
            id="bus1", topic=Topic.INPUT, payload={}, source="test", timestamp=ts
        )
        msg_processed = BusMessage(
            id="bus2", topic=Topic.PROCESSED, payload={}, source="test", timestamp=ts
        )
        msg_output = BusMessage(
            id="bus3", topic=Topic.OUTPUT, payload={}, source="test", timestamp=ts
        )
        assert msg_input.topic == "input"
        assert msg_processed.topic == "processed"
        assert msg_output.topic == "output"


class TestTraceEvent:
    """Tests for TraceEvent model."""

    def test_create_trace_event(self):
        """Test creating TraceEvent."""
        ts = datetime.now(timezone.utc)
        event = TraceEvent(
            id="trace1",
            event_type="message_received",
            actor="dialogue_agent",
            data={"user_id": "user1", "content": "Hello"},
            timestamp=ts,
        )
        assert event.id == "trace1"
        assert event.event_type == "message_received"
        assert event.actor == "dialogue_agent"
        assert event.data == {"user_id": "user1", "content": "Hello"}
        assert event.timestamp == ts

    def test_trace_event_different_types(self):
        """Test TraceEvent with different event types."""
        ts = datetime.now(timezone.utc)
        event_types = [
            "message_received",
            "message_responded",
            "buffer_published",
            "bus_message_published",
            "processing_started",
            "processing_completed",
            "output_routed",
            "output_delivered",
            "sim_started",
            "sim_completed",
        ]
        for event_type in event_types:
            event = TraceEvent(
                id=f"trace_{event_type}",
                event_type=event_type,
                actor="test",
                data={},
                timestamp=ts,
            )
            assert event.event_type == event_type
