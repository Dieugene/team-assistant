"""DialogueBuffer implementation."""

from datetime import datetime

from ..models import DialogueState, Message


class DialogueBuffer:
    """Computed subset of Messages for publication to EventBus."""

    def __init__(self, dialogue_state: DialogueState):
        self._dialogue_state = dialogue_state
        self._messages: list[Message] = []

    def add(self, message: Message) -> None:
        """Add a message to the buffer."""
        self._messages.append(message)

    def get_unpublished(self) -> list[Message]:
        """Get messages after last_published_timestamp."""
        if not self._dialogue_state.last_published_timestamp:
            return self._messages.copy()

        return [
            msg
            for msg in self._messages
            if msg.timestamp > self._dialogue_state.last_published_timestamp
        ]

    def get_all(self) -> list[Message]:
        """Get all messages in buffer."""
        return self._messages.copy()

    def clear(self) -> None:
        """Clear the buffer."""
        self._messages.clear()

    def set_published_timestamp(self, timestamp: datetime) -> None:
        """Update the last published timestamp."""
        self._dialogue_state.last_published_timestamp = timestamp
