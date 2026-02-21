"""Tests for Tracker."""

from datetime import datetime, timezone

import pytest

from core.models import BusMessage, Topic


class TestTrackerTrack:
    """Tests for Tracker.track() method."""

    @pytest.mark.asyncio
    async def test_track_creates_event(self, tracker, storage):
        """Test that track() creates a TraceEvent."""
        await tracker.track(
            event_type="test_event",
            actor="test_actor",
            data={"key": "value"},
        )

        events = await storage.get_trace_events()
        assert len(events) == 1
        assert events[0].event_type == "test_event"
        assert events[0].actor == "test_actor"
        assert events[0].data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_track_generates_id(self, tracker, storage):
        """Test that track() generates ID if not provided."""
        await tracker.track(
            event_type="test_event", actor="test_actor", data={}
        )

        events = await storage.get_trace_events()
        assert events[0].id is not None

    @pytest.mark.asyncio
    async def test_track_generates_timestamp(self, tracker, storage):
        """Test that track() generates timestamp if not provided."""
        before = datetime.now(timezone.utc)
        await tracker.track(
            event_type="test_event", actor="test_actor", data={}
        )
        after = datetime.now(timezone.utc)

        events = await storage.get_trace_events()
        assert before <= events[0].timestamp <= after

    @pytest.mark.asyncio
    async def test_track_multiple_events(self, tracker, storage):
        """Test tracking multiple events."""
        await tracker.track(event_type="event1", actor="actor1", data={})
        await tracker.track(event_type="event2", actor="actor2", data={})
        await tracker.track(event_type="event3", actor="actor3", data={})

        events = await storage.get_trace_events()
        assert len(events) == 3


class TestTrackerSubscription:
    """Tests for Tracker EventBus subscription."""

    @pytest.mark.asyncio
    async def test_subscription_creates_events(self, tracker, event_bus, storage):
        """Test that subscription creates TraceEvents for BusMessages."""
        # Start tracker (subscribes to EventBus)
        await tracker.start()

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={"messages": []},
            source="test_source",
            timestamp=ts,
        )

        await event_bus.publish(msg)

        # Give time for async processing
        import asyncio

        await asyncio.sleep(0.1)

        events = await storage.get_trace_events()
        # Should have trace event from subscription
        bus_events = [e for e in events if e.event_type == "bus_message_published"]
        assert len(bus_events) >= 1

        await tracker.stop()

    @pytest.mark.asyncio
    async def test_subscription_event_data(self, tracker, event_bus, storage):
        """Test that subscription includes correct data in TraceEvent."""
        await tracker.start()

        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1",
            topic=Topic.PROCESSED,
            payload={"output": "test"},
            source="my_agent",
            timestamp=ts,
        )

        await event_bus.publish(msg)

        import asyncio

        await asyncio.sleep(0.1)

        events = await storage.get_trace_events(
            event_types=["bus_message_published"]
        )
        assert len(events) >= 1
        assert events[0].actor == "event_bus"
        assert "topic" in events[0].data
        assert "source" in events[0].data

        await tracker.stop()

    @pytest.mark.asyncio
    async def test_dual_channel_track_and_subscription(
        self, tracker, event_bus, storage
    ):
        """Test that both track() and subscription work simultaneously."""
        await tracker.start()

        # Direct track
        await tracker.track(
            event_type="direct_event", actor="test_actor", data={}
        )

        # Bus message
        ts = datetime.now(timezone.utc)
        msg = BusMessage(
            id="bus1", topic=Topic.INPUT, payload={}, source="test", timestamp=ts
        )
        await event_bus.publish(msg)

        import asyncio

        await asyncio.sleep(0.1)

        events = await storage.get_trace_events()
        assert len(events) >= 2

        await tracker.stop()
