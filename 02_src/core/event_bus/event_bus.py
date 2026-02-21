"""EventBus implementation for pub/sub messaging."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol

from ..logging_config import get_logger
from ..models import BusMessage, Topic
from ..storage import IStorage

logger = get_logger(__name__)


TopicHandler = Callable[[BusMessage], Awaitable[None]]


class IEventBus(Protocol):
    """In-memory pub/sub for exchanging BusMessages."""

    def subscribe(self, topic: Topic, handler: TopicHandler) -> None:
        """Subscribe a handler to a topic."""
        ...

    async def publish(self, message: BusMessage) -> None:
        """Publish BusMessage: calls subscriber callbacks, persists to Storage."""
        ...


class EventBus:
    """In-memory pub/sub event bus."""

    def __init__(self, storage: IStorage):
        self._storage = storage
        self._subscribers: dict[Topic, list[TopicHandler]] = {
            Topic.INPUT: [],
            Topic.PROCESSED: [],
            Topic.OUTPUT: [],
        }

    def subscribe(self, topic: Topic, handler: TopicHandler) -> None:
        """Subscribe a handler to a topic."""
        self._subscribers[topic].append(handler)

    async def publish(self, message: BusMessage) -> None:
        """Publish BusMessage: calls subscriber callbacks, persists to Storage."""
        # Generate ID if not provided
        if not message.id:
            message.id = str(uuid.uuid4())

        # Get subscribers for this topic
        handlers = self._subscribers.get(message.topic, [])

        # Call all handlers concurrently
        if handlers:
            results = await asyncio.gather(
                *[handler(message) for handler in handlers],
                return_exceptions=True,
            )

            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error("Error in handler %s: %s", i, result)

        # Persist to storage
        await self._storage.save_bus_message(message)
