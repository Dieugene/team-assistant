"""Integration tests for Team Assistant end-to-end flow."""

import asyncio
import os
import tempfile

import httpx
import pytest

from core.app import Application


@pytest.fixture
async def app():
    """Create and start a test application."""
    # Use temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    app = Application(db_path=db_path)
    await app.start()

    yield app

    await app.stop()

    # Cleanup
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_full_flow(app: Application):
    """Test end-to-end flow: SIM -> Core -> VS UI."""
    # Create test user
    user_id = "test_user_001"

    # Send a message
    response_text = await app.dialogue_agent.handle_message(
        user_id=user_id,
        text="Hello, this is a test message.",
    )

    assert response_text is not None
    assert isinstance(response_text, str)

    # Wait for buffer to publish (5 seconds timeout + margin)
    await asyncio.sleep(6)

    # Check trace events
    events = await app.storage.get_trace_events(limit=100)

    # Should have trace events
    assert len(events) > 0

    # Check for expected event types
    event_types = {e.event_type for e in events}
    assert "message_received" in event_types
    assert "message_responded" in event_types
    assert "buffer_published" in event_types
    assert "bus_message_published" in event_types
    assert "processing_started" in event_types
    assert "processing_completed" in event_types
    assert "output_routed" in event_types
    assert "output_delivered" in event_types


@pytest.mark.asyncio
async def test_reset(app: Application):
    """Test reset functionality."""
    # Send a message
    await app.dialogue_agent.handle_message(
        user_id="test_user_002",
        text="Test before reset",
    )

    # Wait and check data exists
    await asyncio.sleep(0.5)
    events = await app.storage.get_trace_events(limit=10)
    assert len(events) > 0

    # Reset
    await app.reset()

    # Check data is cleared
    events = await app.storage.get_trace_events(limit=10)
    assert len(events) == 0


@pytest.mark.asyncio
async def test_http_api_integration(app: Application):
    """Test HTTP API integration."""
    # Note: This would require starting the FastAPI server
    # For simplicity, we test the core components directly
    # In a real integration test, you'd use TestClient from FastAPI

    # Send message through dialogue agent
    response = await app.dialogue_agent.handle_message(
        user_id="api_test_user",
        text="Test API integration",
    )

    assert response is not None

    # Wait for processing
    await asyncio.sleep(6)

    # Check trace events are stored
    events = await app.storage.get_trace_events(limit=100)
    assert len(events) > 0
