"""Tracker implementation for creating TraceEvents."""

import uuid
from datetime import datetime, timezone
from typing import Protocol

from ..event_bus import EventBus, IEventBus
from ..models import BusMessage, TraceEvent
from ..storage import IStorage


class ITracker(Protocol):
    """Creating TraceEvents. Two channels: EventBus subscription + direct calls."""

    async def track(self, event_type: str, actor: str, data: dict) -> None:
        """Create TraceEvent and save to Storage."""
        ...

    async def stop(self) -> None:
        """Stop tracker (no-op for now)."""
        ...


class Tracker:
    """Creates TraceEvents via EventBus subscription and direct track() calls."""

    def __init__(self, event_bus: IEventBus, storage: IStorage):
        self._event_bus = event_bus
        self._storage = storage

    async def start(self) -> None:
        """Subscribe to all EventBus topics."""
        from ..models import Topic

        for topic in [Topic.INPUT, Topic.PROCESSED, Topic.OUTPUT]:
            self._event_bus.subscribe(topic, self._handle_bus_message)

    async def _handle_bus_message(self, bus_message: BusMessage) -> None:
        """Handle incoming BusMessage from EventBus."""
        # Extract payload summary (first 100 chars)
        payload_summary = str(bus_message.payload)[:100]

        await self.track(
            event_type="bus_message_published",
            actor="event_bus",
            data={
                "topic": bus_message.topic.value,
                "source": bus_message.source,
                "payload_summary": payload_summary,
            },
        )

    async def track(self, event_type: str, actor: str, data: dict) -> None:
        """Create TraceEvent and save to Storage."""
        trace_event = TraceEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            actor=actor,
            data=data,
            timestamp=datetime.now(timezone.utc),
        )
        await self._storage.save_trace_event(trace_event)

    async def stop(self) -> None:
        """Stop tracker (no-op for MVP)."""
        return
