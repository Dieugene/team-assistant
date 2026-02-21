"""Tests for EventBus."""

from datetime import datetime, timezone

import pytest

from core.models import BusMessage, Topic


class TestEventBusSubscribe:
    """Tests for EventBus subscription."""

    @pytest.mark.asyncio
    async def test_subscribe_single_handler(self, event_bus):
        """Test subscribing a single handler."""
        calls = []

        async def handler(msg: BusMessage):
            calls.append(msg)

        event_bus.subscribe(Topic.INPUT, handler)
        # Verify subscription is stored (internal test)
        assert Topic.INPUT in event_bus._subscribers
        assert len(event_bus._subscribers[Topic.INPUT]) == 1

    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers(self, event_bus):
        """Test subscribing multiple handlers to same topic."""
        calls = []

        async def handler1(msg: BusMessage):
            calls.append(("h1", msg))

        async def handler2(msg: BusMessage):
            calls.append(("h2", msg))

        event_bus.subscribe(Topic.INPUT, handler1)
        event_bus.subscribe(Topic.INPUT, handler2)

        assert len(event_bus._subscribers[Topic.INPUT]) == 2


class TestEventBusPublish:
    """Tests for EventBus publishing."""

    @pytest.mark.asyncio
    async def test_publish_single_subscriber(self, event_bus):
        """Test publishing to a single subscriber."""
        calls = []

        async def handler(msg: BusMessage):
            calls.append(msg)

        event_bus.subscribe(Topic.INPUT, handler)

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={"test": "data"},
            source="test",
            timestamp=ts,
        )

        await event_bus.publish(msg)

        assert len(calls) == 1
        assert calls[0].id == "bus1"
        assert calls[0].payload == {"test": "data"}

    @pytest.mark.asyncio
    async def test_publish_multiple_subscribers(self, event_bus):
        """Test publishing to multiple subscribers."""
        calls = []

        async def handler1(msg: BusMessage):
            calls.append(("h1", msg))

        async def handler2(msg: BusMessage):
            calls.append(("h2", msg))

        event_bus.subscribe(Topic.INPUT, handler1)
        event_bus.subscribe(Topic.INPUT, handler2)

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={},
            source="test",
            timestamp=ts,
        )

        await event_bus.publish(msg)

        assert len(calls) == 2
        assert calls[0][0] == "h1"
        assert calls[1][0] == "h2"

    @pytest.mark.asyncio
    async def test_publish_different_topics(self, event_bus):
        """Test that subscribers only receive messages from their topic."""
        input_calls = []
        output_calls = []

        async def input_handler(msg: BusMessage):
            input_calls.append(msg)

        async def output_handler(msg: BusMessage):
            output_calls.append(msg)

        event_bus.subscribe(Topic.INPUT, input_handler)
        event_bus.subscribe(Topic.OUTPUT, output_handler)

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={},
            source="test",
            timestamp=ts,
        )

        await event_bus.publish(msg)

        assert len(input_calls) == 1
        assert len(output_calls) == 0

    @pytest.mark.asyncio
    async def test_publish_persists_message(self, event_bus, storage):
        """Test that published messages are persisted."""
        calls = []

        async def handler(msg: BusMessage):
            calls.append(msg)

        event_bus.subscribe(Topic.INPUT, handler)

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={"test": "data"},
            source="test_source",
            timestamp=ts,
        )

        await event_bus.publish(msg)

        # Verify message was persisted
        messages = await storage.get_bus_messages()
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_publish_error_in_handler(self, event_bus):
        """Test that errors in one handler don't affect others."""
        calls = []

        async def failing_handler(msg: BusMessage):
            calls.append("failing")
            raise RuntimeError("Test error")

        async def normal_handler(msg: BusMessage):
            calls.append("normal")

        event_bus.subscribe(Topic.INPUT, failing_handler)
        event_bus.subscribe(Topic.INPUT, normal_handler)

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1", topic=Topic.INPUT, payload={}, source="test", timestamp=ts
        )

        # Should not raise error
        await event_bus.publish(msg)

        # Both handlers should have been called
        assert "failing" in calls
        assert "normal" in calls
