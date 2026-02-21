"""Echo ProcessingAgent implementation."""

import uuid
from datetime import datetime, timezone
from typing import Protocol

from ...event_bus import IEventBus
from ...llm import ILLMProvider
from ...logging_config import get_logger
from ...models import BusMessage, Topic
from ...storage import IStorage
from ...tracker import ITracker

logger = get_logger(__name__)


class IProcessingAgent(Protocol):
    """A single processing agent."""

    @property
    def agent_id(self) -> str:
        """Agent identifier."""
        ...

    async def start(self) -> None:
        """Subscribe to needed Topics in EventBus."""
        ...

    async def stop(self) -> None:
        """Unsubscribe from EventBus."""
        ...


class EchoAgent:
    """Minimal echo agent for testing data flow."""

    def __init__(
        self,
        agent_id: str,
        event_bus: IEventBus,
        storage: IStorage,
        llm_provider: ILLMProvider,
        tracker: ITracker,
    ):
        self._agent_id = agent_id
        self._event_bus = event_bus
        self._storage = storage
        self._llm = llm_provider
        self._tracker = tracker

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def start(self) -> None:
        """Subscribe to INPUT topic."""
        self._event_bus.subscribe(Topic.INPUT, self._handle_input)

    async def stop(self) -> None:
        """Unsubscribe (not implemented for MVP)."""
        pass

    async def _handle_input(self, bus_message: BusMessage) -> None:
        """Handle incoming input BusMessage."""
        payload = bus_message.payload
        user_id = payload.get("user_id", "unknown")
        dialogue_id = payload.get("dialogue_id", "unknown")
        messages = payload.get("messages", [])

        await self._tracker.track(
            "processing_started",
            f"agent:{self._agent_id}",
            {"dialogue_id": dialogue_id, "message_count": len(messages)},
        )
        logger.info(
            "EchoAgent %s started processing %s messages from %s",
            self._agent_id,
            len(messages),
            dialogue_id,
        )

        # Form echo output
        output = f"Echo: {len(messages)} messages from {dialogue_id}"

        # Publish to OUTPUT
        output_message = BusMessage(
            id=str(uuid.uuid4()),
            topic=Topic.OUTPUT,
            payload={
                "user_id": user_id,
                "content": output,
            },
            source=self._agent_id,
            timestamp=datetime.now(timezone.utc),
        )

        await self._event_bus.publish(output_message)

        await self._tracker.track(
            "processing_completed",
            f"agent:{self._agent_id}",
            {"dialogue_id": dialogue_id, "output": output},
        )
        logger.info(
            "EchoAgent %s completed processing: %s",
            self._agent_id,
            output,
        )
