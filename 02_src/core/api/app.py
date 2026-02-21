"""FastAPI application setup."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..app import Application
from .routes import control, messaging, observability


# Global application instance
_app: Application | None = None


def get_app() -> Application:
    """Get the global application instance."""
    global _app
    if not _app:
        _app = Application()
    return _app


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    application = get_app()
    await application.start()
    sim_instance = control.get_sim_instance()
    if sim_instance and hasattr(sim_instance, "set_tracker"):
        if application._tracker:
            sim_instance.set_tracker(application._tracker)
    yield
    # Shutdown
    await application.stop()


def create_fastapi_app() -> FastAPI:
    """Create and configure FastAPI application."""
    fastapi_app = FastAPI(
        title="Team Assistant API",
        description="Core API for Team Assistant system",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Enable CORS
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Vite default
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application = get_app()
    fastapi_app.include_router(messaging.create_messaging_router(application))
    fastapi_app.include_router(observability.create_observability_router(application))
    fastapi_app.include_router(control.create_control_router(application))

    return fastapi_app
