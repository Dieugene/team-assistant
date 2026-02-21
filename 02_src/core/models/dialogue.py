"""Dialogue-related data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DialogueState:
    """Persistent state of a dialogue for buffer recovery."""

    user_id: str
    dialogue_id: str
    last_published_timestamp: datetime | None = None
