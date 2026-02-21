"""DialogueAgent implementation."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Protocol

from ..event_bus import IEventBus
from ..llm import ILLMProvider
from ..logging_config import get_logger
from ..models import BusMessage, DialogueState, Message, Topic
from ..storage import IStorage
from ..tracker import ITracker
from .buffer import DialogueBuffer

logger = get_logger(__name__)


class IDialogueAgent(Protocol):
    """Managing all Dialogues."""

    async def handle_message(self, user_id: str, text: str) -> str:
        """Accept Message from User, generate response via LLM, save both to Storage, add to DialogueBuffer. Return response text."""
        ...

    async def deliver_output(self, user_id: str, content: str) -> None:
        """Deliver output from OutputRouter to user. Save as system Message."""
        ...

    async def start(self) -> None:
        """Restore DialogueState from Storage."""
        ...

    async def stop(self) -> None:
        """Save DialogueState, stop accepting messages."""
        ...


class DialogueAgent:
    """Manages dialogues with users."""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        event_bus: IEventBus,
        storage: IStorage,
        tracker: ITracker,
    ):
        self._llm = llm_provider
        self._event_bus = event_bus
        self._storage = storage
        self._tracker = tracker

        # In-memory storage
        self._buffers: dict[str, DialogueBuffer] = {}
        self._dialogue_ids: dict[str, str] = {}  # user_id -> dialogue_id
        self._buffer_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Restore DialogueState from Storage."""
        logger.info("Starting DialogueAgent")
        self._running = True

    async def stop(self) -> None:
        """Save DialogueState, stop accepting messages."""
        logger.info("Stopping DialogueAgent")
        self._running = False

        # Cancel all buffer tasks
        for task in self._buffer_tasks.values():
            task.cancel()

        # Save all dialogue states
        for user_id, buffer in self._buffers.items():
            dialogue_id = self._dialogue_ids.get(user_id, str(uuid.uuid4()))
            state = DialogueState(
                user_id=user_id,
                dialogue_id=dialogue_id,
                last_published_timestamp=buffer._dialogue_state.last_published_timestamp,
            )
            await self._storage.save_dialogue_state(state)

    async def handle_message(self, user_id: str, text: str) -> str:
        """Accept Message from User, generate response via LLM, save both to Storage."""
        if not self._running:
            raise RuntimeError("DialogueAgent not started")

        logger.info(f"Message received from {user_id}: {text[:100]}...")

        # Get or create dialogue_id
        state = None
        if user_id not in self._dialogue_ids:
            state = await self._storage.get_dialogue_state(user_id)
            if state:
                self._dialogue_ids[user_id] = state.dialogue_id
            else:
                self._dialogue_ids[user_id] = str(uuid.uuid4())

        dialogue_id = self._dialogue_ids[user_id]

        # Get or create buffer
        if user_id not in self._buffers:
            if state is None:
                state = await self._storage.get_dialogue_state(user_id)
            if not state:
                state = DialogueState(user_id=user_id, dialogue_id=dialogue_id)
            self._buffers[user_id] = DialogueBuffer(state)

            # Start background timer for this user
            self._buffer_tasks[user_id] = asyncio.create_task(
                self._buffer_timer(user_id)
            )

        buffer = self._buffers[user_id]

        # Create user message
        user_message = Message(
            id=str(uuid.uuid4()),
            dialogue_id=dialogue_id,
            role="user",
            content=text,
            timestamp=datetime.now(timezone.utc),
        )

        await self._storage.save_message(user_message)
        buffer.add(user_message)

        await self._tracker.track(
            event_type="message_received",
            actor="dialogue_agent",
            data={
                "user_id": user_id,
                "dialogue_id": dialogue_id,
                "message_text": text,
            },
        )

        # Get dialogue context
        all_messages = await self._storage.get_messages(dialogue_id)
        context = [
            {"role": msg.role, "content": msg.content} for msg in all_messages
        ]

        # Generate response
        try:
            response_text = await self._llm.complete(messages=context)
            logger.debug(f"Generated response for {user_id}: {response_text[:50]}...")
        except Exception as e:
            logger.error(f"LLM error for {user_id}: {e}", exc_info=True)
            response_text = "Извините, произошла ошибка при генерации ответа."

        # Create assistant message
        assistant_message = Message(
            id=str(uuid.uuid4()),
            dialogue_id=dialogue_id,
            role="assistant",
            content=response_text,
            timestamp=datetime.now(timezone.utc),
        )

        await self._storage.save_message(assistant_message)
        buffer.add(assistant_message)

        await self._tracker.track(
            event_type="message_responded",
            actor="dialogue_agent",
            data={
                "user_id": user_id,
                "dialogue_id": dialogue_id,
                "response_text": response_text,
            },
        )

        return response_text

    async def deliver_output(self, user_id: str, content: str) -> None:
        """Deliver output from OutputRouter to user."""
        if not self._running:
            raise RuntimeError("DialogueAgent not started")

        # Get or create dialogue_id
        if user_id not in self._dialogue_ids:
            self._dialogue_ids[user_id] = str(uuid.uuid4())

        dialogue_id = self._dialogue_ids[user_id]

        # Create system message
        system_message = Message(
            id=str(uuid.uuid4()),
            dialogue_id=dialogue_id,
            role="system",
            content=content,
            timestamp=datetime.now(timezone.utc),
        )

        await self._storage.save_message(system_message)

        await self._tracker.track(
            event_type="output_delivered",
            actor="dialogue_agent",
            data={
                "user_id": user_id,
                "content": content,
            },
        )

    async def _buffer_timer(self, user_id: str) -> None:
        """Background timer for publishing buffered messages."""
        while self._running:
            try:
                await asyncio.sleep(5)  # 5 second timeout

                if user_id not in self._buffers:
                    continue

                buffer = self._buffers[user_id]
                unpublished = buffer.get_unpublished()

                if unpublished:
                    # Publish to EventBus
                    bus_message = BusMessage(
                        id=str(uuid.uuid4()),
                        topic=Topic.INPUT,
                        payload={
                            "user_id": user_id,
                            "dialogue_id": self._dialogue_ids[user_id],
                            "messages": [
                                {
                                    "id": msg.id,
                                    "role": msg.role,
                                    "content": msg.content,
                                    "timestamp": msg.timestamp.isoformat(),
                                }
                                for msg in unpublished
                            ],
                        },
                        source="dialogue_agent",
                        timestamp=datetime.now(timezone.utc),
                    )

                    await self._event_bus.publish(bus_message)

                    # Update published timestamp
                    buffer.set_published_timestamp(datetime.now(timezone.utc))

                    await self._tracker.track(
                        event_type="buffer_published",
                        actor="dialogue_agent",
                        data={
                            "user_id": user_id,
                            "dialogue_id": self._dialogue_ids[user_id],
                            "message_count": len(unpublished),
                        },
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Buffer timer error for {user_id}: {e}", exc_info=True)
