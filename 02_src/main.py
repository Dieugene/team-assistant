"""Main entry point for Team Assistant Core."""

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from core.api import create_fastapi_app
from sim import Sim


def main():
    """Run the application."""
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    # Get configuration from environment
    api_host = os.getenv("API_HOST", "localhost")
    api_port = int(os.getenv("API_PORT", "8000"))
    api_url = f"http://{api_host}:{api_port}"

    # Create SIM instance
    sim = Sim(api_url=api_url)

    # Set SIM instance for control router
    from core.api.routes import control
    control.set_sim_instance(sim)

    # Create FastAPI app
    app = create_fastapi_app()

    # Run with uvicorn
    uvicorn.run(
        app,
        host=api_host,
        port=api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
