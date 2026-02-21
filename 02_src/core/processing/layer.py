"""ProcessingLayer implementation."""

from typing import Protocol

from ..event_bus import IEventBus
from ..llm import ILLMProvider
from ..storage import IStorage
from ..tracker import ITracker
from .agents.echo_agent import IProcessingAgent


class IProcessingLayer(Protocol):
    """Managing ProcessingAgent lifecycle."""

    async def start(self) -> None:
        """Start all registered agents."""
        ...

    async def stop(self) -> None:
        """Stop all agents."""
        ...

    def register_agent(self, agent: IProcessingAgent) -> None:
        """Register an agent."""
        ...


class ProcessingLayer:
    """Manages ProcessingAgent lifecycle."""

    def __init__(
        self,
        event_bus: IEventBus,
        storage: IStorage,
        tracker: ITracker,
        llm_provider: ILLMProvider,
    ):
        self._event_bus = event_bus
        self._storage = storage
        self._tracker = tracker
        self._llm = llm_provider
        self._agents: list[IProcessingAgent] = []

    def register_agent(self, agent: IProcessingAgent) -> None:
        """Register an agent."""
        self._agents.append(agent)

    async def start(self) -> None:
        """Start all registered agents."""
        for agent in self._agents:
            await agent.start()

    async def stop(self) -> None:
        """Stop all agents."""
        for agent in self._agents:
            await agent.stop()
