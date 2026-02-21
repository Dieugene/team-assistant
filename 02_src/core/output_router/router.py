"""OutputRouter implementation."""

from typing import Protocol

from ..dialogue import IDialogueAgent
from ..event_bus import IEventBus
from ..models import BusMessage, Topic
from ..tracker import ITracker


class IOutputRouter(Protocol):
    """Preprocessing of output before delivery."""

    async def start(self) -> None:
        """Subscribe to EventBus topic: OUTPUT."""
        ...

    async def stop(self) -> None:
        """Unsubscribe from EventBus."""
        ...


class OutputRouter:
    """Routes output messages to users (passthrough in MVP)."""

    def __init__(
        self,
        event_bus: IEventBus,
        dialogue_agent: IDialogueAgent,
        tracker: ITracker,
    ):
        self._event_bus = event_bus
        self._dialogue_agent = dialogue_agent
        self._tracker = tracker

    async def start(self) -> None:
        """Subscribe to OUTPUT topic."""
        self._event_bus.subscribe(Topic.OUTPUT, self._handle_output)

    async def stop(self) -> None:
        """Unsubscribe (not implemented for MVP)."""
        pass

    async def _handle_output(self, bus_message: BusMessage) -> None:
        """Handle incoming output BusMessage (passthrough in MVP)."""
        payload = bus_message.payload
        user_id = payload.get("user_id", "unknown")
        content = payload.get("content", "")

        await self._tracker.track(
            event_type="output_routed",
            actor="output_router",
            data={
                "target_user_id": user_id,
                "content_summary": content[:100],
            },
        )

        # Deliver to user
        await self._dialogue_agent.deliver_output(user_id, content)
