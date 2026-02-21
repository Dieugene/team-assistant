"""Control API routes."""

from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ...app import IApplication


router = APIRouter(prefix="/api/control", tags=["control"])


class StatusResponse(BaseModel):
    """Response model for status."""

    status: str


# Global SIM instance (will be set by main app)
_sim_instance: Any = None


def set_sim_instance(sim: Any) -> None:
    """Set the global SIM instance."""
    global _sim_instance
    _sim_instance = sim


def get_sim_instance() -> Any:
    """Get the global SIM instance."""
    return _sim_instance


def create_control_router(app: IApplication) -> APIRouter:
    """Create control router."""

    @router.post("/reset", response_model=StatusResponse)
    async def reset_system() -> dict:
        """Reset system data between test runs."""
        try:
            await app.reset()
            return {"status": "ok"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/sim/start", response_model=StatusResponse)
    async def start_sim() -> dict:
        """Start SIM simulation."""
        try:
            if _sim_instance:
                await _sim_instance.start()
                return {"status": "ok"}
            else:
                raise HTTPException(status_code=404, detail="SIM not configured")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/sim/stop", response_model=StatusResponse)
    async def stop_sim() -> dict:
        """Stop SIM simulation."""
        try:
            if _sim_instance:
                await _sim_instance.stop()
                return {"status": "ok"}
            else:
                raise HTTPException(status_code=404, detail="SIM not configured")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
