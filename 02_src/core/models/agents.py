"""Agent-related data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Topic(str, Enum):
    """EventBus topics."""

    INPUT = "input"
    PROCESSED = "processed"
    OUTPUT = "output"


@dataclass
class AgentState:
    """Persistent state of a ProcessingAgent."""

    agent_id: str
    data: dict  # key-value storage
    sgr_traces: list[dict] = field(default_factory=list)  # reasoning traces


@dataclass
class BusMessage:
    """A message exchanged through EventBus."""

    id: str
    topic: Topic
    payload: dict  # varies by topic
    source: str  # component that published
    timestamp: datetime
