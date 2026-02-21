"""Messaging API routes."""

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ...app import IApplication


router = APIRouter(prefix="/api", tags=["messaging"])


class MessageRequest(BaseModel):
    """Request model for sending a message."""

    user_id: str
    text: str


class MessageResponse(BaseModel):
    """Response model for message."""

    response: str


def create_messaging_router(app: IApplication) -> APIRouter:
    """Create messaging router."""

    @router.post("/messages", response_model=MessageResponse)
    async def send_message(request: MessageRequest) -> dict:
        """Send a message to the dialogue agent."""
        try:
            response = await app.dialogue_agent.handle_message(
                user_id=request.user_id, text=request.text
            )
            return {"response": response}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
