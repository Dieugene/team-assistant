"""Tests for OutputRouter."""

import pytest

from core.models import BusMessage, Topic
from core.output_router import OutputRouter


class TestOutputRouterInit:
    """Tests for OutputRouter initialization."""

    def test_init(self, event_bus, dialogue_agent, tracker):
        """Test creating OutputRouter."""
        router = OutputRouter(
            event_bus=event_bus,
            dialogue_agent=dialogue_agent,
            tracker=tracker,
        )
        assert router is not None


class TestOutputRouterStart:
    """Tests for OutputRouter.start()."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_output(self, event_bus, dialogue_agent, tracker):
        """Test that start subscribes to OUTPUT topic."""
        router = OutputRouter(
            event_bus=event_bus,
            dialogue_agent=dialogue_agent,
            tracker=tracker,
        )
        await router.start()

        # Check subscription
        assert Topic.OUTPUT in event_bus._subscribers
        handlers = event_bus._subscribers[Topic.OUTPUT]
        assert len(handlers) >= 1


class TestOutputRouterHandle:
    """Tests for OutputRouter._handle_output()."""

    @pytest.mark.asyncio
    async def test_handle_output_delivers_to_dialogue_agent(
        self, event_bus, dialogue_agent, tracker, storage
    ):
        """Test that _handle_output delivers to DialogueAgent."""
        router = OutputRouter(
            event_bus=event_bus,
            dialogue_agent=dialogue_agent,
            tracker=tracker,
        )
        await router.start()

        # Publish output message
        ts = datetime.now(timezone.utc)
        output_msg = BusMessage(
            id="bus1",
            topic=Topic.OUTPUT,
            payload={"user_id": "user1", "content": "Test output"},
            source="echo_agent",
            timestamp=ts,
        )

        await event_bus.publish(output_msg)

        # Give time for async processing
        import asyncio

        await asyncio.sleep(0.1)

        # Verify message was delivered to user
        messages = await storage.get_messages(dialogue_agent._dialogue_ids["user1"])
        system_msgs = [m for m in messages if m.role == "system"]
        assert len(system_msgs) >= 1
        assert system_msgs[0].content == "Test output"

    @pytest.mark.asyncio
    async def test_handle_output_tracks_event(
        self, event_bus, dialogue_agent, tracker, storage
    ):
        """Test that _handle_output tracks TraceEvent."""
        router = OutputRouter(
            event_bus=event_bus,
            dialogue_agent=dialogue_agent,
            tracker=tracker,
        )
        await router.start()

        ts = datetime.now(timezone.utc)
        output_msg = BusMessage(
            id="bus1",
            topic=Topic.OUTPUT,
            payload={"user_id": "user1", "content": "Test"},
            source="test",
            timestamp=ts,
        )

        await event_bus.publish(output_msg)

        import asyncio

        await asyncio.sleep(0.1)

        # Check tracked event
        events = await storage.get_trace_events(
            event_types=["output_routed"], actor="output_router"
        )
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_handle_output_passthrough(
        self, event_bus, dialogue_agent, tracker, storage
    ):
        """Test that _handle_output performs passthrough (no modification)."""
        router = OutputRouter(
            event_bus=event_bus,
            dialogue_agent=dialogue_agent,
            tracker=tracker,
        )
        await router.start()

        original_content = "Original output content"
        ts = datetime.now(timezone.utc)
        output_msg = BusMessage(
            id="bus1",
            topic=Topic.OUTPUT,
            payload={"user_id": "user1", "content": original_content},
            source="test",
            timestamp=ts,
        )

        await event_bus.publish(output_msg)

        import asyncio

        await asyncio.sleep(0.1)

        # Verify content was not modified
        messages = await storage.get_messages(dialogue_agent._dialogue_ids["user1"])
        system_msgs = [m for m in messages if m.role == "system"]
        assert len(system_msgs) >= 1
        assert system_msgs[0].content == original_content

    @pytest.mark.asyncio
    async def test_handle_output_extracts_user_id(
        self, event_bus, dialogue_agent, tracker, storage
    ):
        """Test that _handle_output extracts user_id from payload."""
        router = OutputRouter(
            event_bus=event_bus,
            dialogue_agent=dialogue_agent,
            tracker=tracker,
        )
        await router.start()

        ts = datetime.now(timezone.utc)
        output_msg = BusMessage(
            id="bus1",
            topic=Topic.OUTPUT,
            payload={"user_id": "custom_user", "content": "Test"},
            source="test",
            timestamp=ts,
        )

        await event_bus.publish(output_msg)

        import asyncio

        await asyncio.sleep(0.1)

        # Verify message was delivered to correct user
        messages = await storage.get_messages(dialogue_agent._dialogue_ids["custom_user"])
        assert len(messages) >= 1


# Need to import datetime
from datetime import datetime, timezone
