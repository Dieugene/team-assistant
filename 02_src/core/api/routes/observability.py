"""Observability API routes."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query

from ...app import IApplication


router = APIRouter(prefix="/api", tags=["observability"])


class TraceEventResponse(BaseModel):
    """Response model for trace event."""

    id: str
    event_type: str
    actor: str
    data: dict[str, Any]
    timestamp: datetime


def create_observability_router(app: IApplication) -> APIRouter:
    """Create observability router."""

    @router.get("/trace-events", response_model=list[TraceEventResponse])
    async def get_trace_events(
        after: str | None = Query(None, description="ISO timestamp filter"),
        limit: int = Query(100, ge=1, le=1000),
        event_type: str | None = Query(None, description="Filter by event type"),
        actor: str | None = Query(None, description="Filter by actor"),
    ) -> list[dict]:
        """Get trace events with optional filters."""
        try:
            # Parse after timestamp
            after_dt = None
            if after:
                try:
                    after_dt = datetime.fromisoformat(after)
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid after timestamp format"
                    )

            # Parse event_types
            event_types = [event_type] if event_type else None

            # Get events
            events = await app.storage.get_trace_events(
                after=after_dt,
                event_types=event_types,
                actor=actor,
                limit=limit,
            )

            # Convert to response format
            return [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "data": e.data,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in events
            ]

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
