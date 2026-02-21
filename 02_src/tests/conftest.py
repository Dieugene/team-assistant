"""Pytest configuration and fixtures."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest_asyncio.fixture
async def storage():
    """Create in-memory storage for testing."""
    from core.storage import Storage

    st = Storage(":memory:")
    await st.init()
    yield st
    await st.close()




@pytest.fixture
def event_bus(storage):
    """Create EventBus with storage."""
    from core.event_bus import EventBus
    from core.models import Topic

    eb = EventBus(storage)
    # Don't start automatically - let tests control it
    return eb


@pytest.fixture
def tracker(storage, event_bus):
    """Create Tracker with storage and event bus."""
    from core.tracker import Tracker

    tr = Tracker(event_bus=event_bus, storage=storage)
    return tr


@pytest.fixture
def mock_llm():
    """Create mock LLM provider."""
    llm = Mock()
    llm.complete = AsyncMock(return_value="Test response")
    return llm


@pytest.fixture
async def dialogue_agent(storage, event_bus, tracker, mock_llm):
    """Create DialogueAgent for testing."""
    from core.dialogue.agent import DialogueAgent

    da = DialogueAgent(
        llm_provider=mock_llm,
        event_bus=event_bus,
        storage=storage,
        tracker=tracker,
    )
    await da.start()
    yield da
    await da.stop()


@pytest.fixture
async def processing_layer(storage, event_bus, tracker, mock_llm):
    """Create ProcessingLayer for testing."""
    from core.processing.layer import ProcessingLayer

    pl = ProcessingLayer(
        event_bus=event_bus,
        storage=storage,
        tracker=tracker,
        llm_provider=mock_llm,
    )
    await pl.start()
    yield pl
    await pl.stop()


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    import logging

    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    return logger
