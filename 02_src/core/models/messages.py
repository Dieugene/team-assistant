"""Message-related data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Team:
    """A team containing users."""

    id: str
    name: str


@dataclass
class User:
    """A user participating in a team."""

    id: str
    team_id: str
    name: str


@dataclass
class Attachment:
    """An attachment to a message (file, image, audio)."""

    id: str
    message_id: str
    type: str  # "file", "image", "audio"
    data: bytes | None = None
    url: str | None = None


@dataclass
class Message:
    """A single message in a dialogue."""

    id: str
    dialogue_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    attachments: list[Attachment] = field(default_factory=list)
