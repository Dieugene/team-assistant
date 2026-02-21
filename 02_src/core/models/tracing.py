"""Tracing and observability data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TraceEvent:
    """A single observability event for VS UI."""

    id: str
    event_type: str  # e.g. "message_received", "bus_published"
    actor: str  # who created this event
    data: dict  # full self-contained data for display
    timestamp: datetime
