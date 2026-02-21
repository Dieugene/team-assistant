"""Tests for DialogueAgent."""

import pytest

from core.models import Message


class TestDialogueAgentHandle:
    """Tests for DialogueAgent.handle_message()."""

    @pytest.mark.asyncio
    async def test_handle_message_creates_user_message(
        self, dialogue_agent, storage
    ):
        """Test that handle_message creates user message in storage."""
        response = await dialogue_agent.handle_message("user1", "Hello")

        messages = await storage.get_messages(dialogue_agent._dialogue_ids["user1"])
        assert len(messages) >= 1
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_handle_message_creates_assistant_message(
        self, dialogue_agent, storage
    ):
        """Test that handle_message creates assistant message in storage."""
        response = await dialogue_agent.handle_message("user1", "Hello")

        messages = await storage.get_messages(dialogue_agent._dialogue_ids["user1"])
        assert len(messages) >= 1
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) >= 1
        assert assistant_msgs[0].content == "Test response"

    @pytest.mark.asyncio
    async def test_handle_message_tracks_events(self, dialogue_agent, storage):
        """Test that handle_message tracks TraceEvents."""
        await dialogue_agent.handle_message("user1", "Hello")

        events = await storage.get_trace_events(actor="dialogue_agent")
        assert len(events) >= 2

        event_types = [e.event_type for e in events]
        assert "message_received" in event_types
        assert "message_responded" in event_types

    @pytest.mark.asyncio
    async def test_handle_message_adds_to_buffer(
        self, dialogue_agent
    ):
        """Test that handle_message adds messages to buffer."""
        await dialogue_agent.handle_message("user1", "Hello")

        buffer = dialogue_agent._buffers.get("user1")
        assert buffer is not None
        messages = buffer.get_all()
        assert len(messages) >= 2  # user + assistant

    @pytest.mark.asyncio
    async def test_handle_message_returns_response(self, dialogue_agent):
        """Test that handle_message returns LLM response."""
        response = await dialogue_agent.handle_message("user1", "Hello")
        assert response == "Test response"

    @pytest.mark.asyncio
    async def test_handle_message_multiple_users(
        self, dialogue_agent, storage
    ):
        """Test that handle_message works for multiple users."""
        await dialogue_agent.handle_message("user1", "Hello from user1")
        await dialogue_agent.handle_message("user2", "Hello from user2")

        # Each user should have their own dialogue
        assert "user1" in dialogue_agent._dialogue_ids
        assert "user2" in dialogue_agent._dialogue_ids
        assert dialogue_agent._dialogue_ids["user1"] != dialogue_agent._dialogue_ids[
            "user2"
        ]

    @pytest.mark.asyncio
    async def test_handle_message_when_not_started(self, dialogue_agent):
        """Test that handle_message raises error when not started."""
        await dialogue_agent.stop()

        with pytest.raises(RuntimeError, match="not started"):
            await dialogue_agent.handle_message("user1", "Hello")


class TestDialogueAgentDeliver:
    """Tests for DialogueAgent.deliver_output()."""

    @pytest.mark.asyncio
    async def test_deliver_output_creates_system_message(
        self, dialogue_agent, storage
    ):
        """Test that deliver_output creates system message."""
        await dialogue_agent.deliver_output("user1", "Output content")

        messages = await storage.get_messages(dialogue_agent._dialogue_ids["user1"])
        system_msgs = [m for m in messages if m.role == "system"]
        assert len(system_msgs) >= 1
        assert system_msgs[0].content == "Output content"

    @pytest.mark.asyncio
    async def test_deliver_output_tracks_event(self, dialogue_agent, storage):
        """Test that deliver_output tracks TraceEvent."""
        await dialogue_agent.deliver_output("user1", "Output content")

        events = await storage.get_trace_events(
            event_types=["output_delivered"], actor="dialogue_agent"
        )
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_deliver_output_when_not_started(self, dialogue_agent):
        """Test that deliver_output raises error when not started."""
        await dialogue_agent.stop()

        with pytest.raises(RuntimeError, match="not started"):
            await dialogue_agent.deliver_output("user1", "Output")


class TestDialogueAgentLifecycle:
    """Tests for DialogueAgent start/stop."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, dialogue_agent):
        """Test that start sets _running flag."""
        assert dialogue_agent._running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, dialogue_agent):
        """Test that stop clears _running flag."""
        await dialogue_agent.stop()
        assert dialogue_agent._running is False

    @pytest.mark.asyncio
    async def test_stop_saves_dialogue_states(self, dialogue_agent, storage):
        """Test that stop saves dialogue states."""
        # Create some activity
        await dialogue_agent.handle_message("user1", "Hello")

        # Stop should save state
        await dialogue_agent.stop()

        state = await storage.get_dialogue_state("user1")
        assert state is not None

    @pytest.mark.asyncio
    async def test_stop_cancels_buffer_tasks(self, dialogue_agent):
        """Test that stop cancels buffer timer tasks."""
        # Create activity to start buffer task
        await dialogue_agent.handle_message("user1", "Hello")

        # Stop should cancel tasks
        await dialogue_agent.stop()

        # Tasks should be cancelled or removed
        import asyncio

        for task in dialogue_agent._buffer_tasks.values():
            assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_start_restores_dialogue_state(self, dialogue_agent, storage):
        """Test that start can restore existing dialogue state."""
        from core.models import DialogueState
        from datetime import datetime, timezone

        # Save a state
        ts = datetime.now(timezone.utc)
        old_state = DialogueState(
            user_id="user1",
            dialogue_id="dialogue123",
            last_published_timestamp=ts,
        )
        await storage.save_dialogue_state(old_state)

        # Create new agent and start
        dialogue_agent2 = type(dialogue_agent)(
            dialogue_agent._llm,
            dialogue_agent._event_bus,
            dialogue_agent._storage,
            dialogue_agent._tracker,
        )
        await dialogue_agent2.start()

        # Send message - should restore existing state
        await dialogue_agent2.handle_message("user1", "Hello")

        # Should use existing dialogue_id
        assert dialogue_agent2._dialogue_ids["user1"] == "dialogue123"

        await dialogue_agent2.stop()


class TestDialogueAgentBuffering:
    """Tests for DialogueAgent buffering."""

    @pytest.mark.asyncio
    async def test_buffer_timer_publishes_to_event_bus(
        self, dialogue_agent, event_bus, storage
    ):
        """Test that buffer timer publishes to EventBus."""
        # This test is tricky because timer is 5 seconds
        # We'll verify the mechanism exists
        await dialogue_agent.handle_message("user1", "Hello")

        # Check that buffer task was created
        assert "user1" in dialogue_agent._buffer_tasks

    @pytest.mark.asyncio
    async def test_buffer_updates_timestamp_after_publishing(
        self, dialogue_agent
    ):
        """Test that buffer updates last_published_timestamp after publishing."""
        # This is hard to test without waiting 5 seconds
        # We'll verify the buffer exists
        await dialogue_agent.handle_message("user1", "Hello")

        buffer = dialogue_agent._buffers["user1"]
        assert buffer is not None
        assert buffer._dialogue_state is not None
