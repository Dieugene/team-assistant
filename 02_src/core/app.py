"""Application bootstrap and lifecycle management."""

import os
from typing import Protocol

from .config import resolve_db_path
from .dialogue.agent import DialogueAgent, IDialogueAgent
from .event_bus import EventBus
from .logging_config import get_logger
from .llm import ILLMProvider, LLMProvider
from .processing import IProcessingLayer, ProcessingLayer
from .processing.agents.echo_agent import EchoAgent
from .output_router import OutputRouter
from .storage import IStorage, Storage
from .tracker import ITracker, Tracker

logger = get_logger(__name__)


class IApplication(Protocol):
    """Bootstrap and lifecycle."""

    async def start(self) -> None:
        """Initialize components in dependency order."""
        ...

    async def stop(self) -> None:
        """Shutdown in reverse order."""
        ...

    async def reset(self) -> None:
        """Reset data between test runs."""
        ...


class Application:
    """Main application bootstrap."""

    def __init__(self, db_path: str | None = None):
        env_db_path = os.getenv("DATABASE_URL") if db_path is None else db_path
        self._db_path = resolve_db_path(env_db_path)

        # Components (will be initialized in start())
        self._storage: IStorage | None = None
        self._event_bus: EventBus | None = None
        self._tracker: ITracker | None = None
        self._llm: ILLMProvider | None = None
        self._output_router: OutputRouter | None = None
        self._processing_layer: IProcessingLayer | None = None
        self._dialogue_agent: IDialogueAgent | None = None

    async def start(self) -> None:
        """Initialize components in dependency order."""
        logger.info("Starting application")

        # 1. Storage (no dependencies)
        self._storage = Storage(self._db_path)
        await self._storage.init()
        logger.info("Storage initialized")

        # 2. EventBus (depends on Storage for persistence)
        self._event_bus = EventBus(self._storage)
        logger.info("EventBus initialized")

        # 3. Tracker (depends on EventBus + Storage)
        self._tracker = Tracker(self._event_bus, self._storage)
        await self._tracker.start()

        # 4. LLMProvider (no internal dependencies)
        self._llm = LLMProvider()
        logger.info("LLM provider initialized")

        # 5. OutputRouter (depends on EventBus)
        # Note: will be set after DialogueAgent is created
        # For now, create placeholder
        self._output_router = None

        # 6. ProcessingLayer (depends on EventBus, Storage, LLM, Tracker)
        self._processing_layer = ProcessingLayer(
            self._event_bus,
            self._storage,
            self._tracker,
            self._llm,
        )
        # Register EchoAgent
        echo_agent = EchoAgent(
            agent_id="echo_agent",
            event_bus=self._event_bus,
            storage=self._storage,
            llm_provider=self._llm,
            tracker=self._tracker,
        )
        self._processing_layer.register_agent(echo_agent)
        await self._processing_layer.start()
        logger.info("ProcessingLayer started with echo_agent")

        # 7. DialogueAgent (depends on LLM, EventBus, Storage, Tracker)
        self._dialogue_agent = DialogueAgent(
            llm_provider=self._llm,
            event_bus=self._event_bus,
            storage=self._storage,
            tracker=self._tracker,
        )
        await self._dialogue_agent.start()
        logger.info("DialogueAgent started")

        # Now create OutputRouter (depends on DialogueAgent)
        self._output_router = OutputRouter(
            event_bus=self._event_bus,
            dialogue_agent=self._dialogue_agent,
            tracker=self._tracker,
        )
        await self._output_router.start()
        logger.info("OutputRouter started")
        logger.info("All components initialized successfully")

    async def stop(self) -> None:
        """Shutdown in reverse order."""
        if self._output_router:
            await self._output_router.stop()
        if self._dialogue_agent:
            await self._dialogue_agent.stop()
        if self._processing_layer:
            await self._processing_layer.stop()
        if self._llm:
            pass  # LLM has no stop method
        if self._tracker:
            pass  # Tracker has no stop method
        if self._event_bus:
            pass  # EventBus has no stop method
        if self._storage:
            await self._storage.close()
            logger.info("Storage closed")

    async def reset(self) -> None:
        """Reset data between test runs."""
        # 1. Pause active processes
        if self._dialogue_agent:
            await self._dialogue_agent.stop()
        if self._processing_layer:
            await self._processing_layer.stop()

        # 2. Clear storage
        if self._storage:
            await self._storage.clear()
            logger.info("Storage cleared")

        # 3. Reset dialogue agent buffers and restart
        if self._dialogue_agent:
            await self._dialogue_agent.start()

        # 4. Restart processing layer
        if self._processing_layer:
            await self._processing_layer.start()
            logger.info("Reset complete")

    @property
    def storage(self) -> IStorage:
        """Get storage instance."""
        if not self._storage:
            raise RuntimeError("Application not started")
        return self._storage

    @property
    def dialogue_agent(self) -> DialogueAgent:
        """Get dialogue agent instance."""
        if not self._dialogue_agent:
            raise RuntimeError("Application not started")
        return self._dialogue_agent

    @property
    def processing_layer(self) -> IProcessingLayer:
        """Get processing layer instance."""
        if not self._processing_layer:
            raise RuntimeError("Application not started")
        return self._processing_layer
