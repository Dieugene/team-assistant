"""Tests for Application."""

import pytest

from core.app import Application


class TestApplicationStart:
    """Tests for Application.start()."""

    @pytest.mark.asyncio
    async def test_start_initializes_components(self):
        """Test that start initializes all components."""
        app = Application(db_path=":memory:")
        await app.start()

        # Check all components are initialized
        assert app._storage is not None
        assert app._event_bus is not None
        assert app._tracker is not None
        assert app._llm is not None
        assert app._output_router is not None
        assert app._processing_layer is not None
        assert app._dialogue_agent is not None

    @pytest.mark.asyncio
    async def test_start_initializes_in_correct_order(self):
        """Test that components are initialized in dependency order."""
        app = Application(db_path=":memory:")
        await app.start()

        # Storage should be first
        assert app._storage is not None

        # EventBus depends on Storage
        assert app._event_bus is not None

        # Tracker depends on EventBus + Storage
        assert app._tracker is not None
        assert app._tracker._event_bus is app._event_bus
        assert app._tracker._storage is app._storage

        # LLM has no dependencies
        assert app._llm is not None

        # ProcessingLayer depends on EventBus, Storage, LLM
        assert app._processing_layer is not None

        # DialogueAgent depends on LLM, EventBus, Storage, Tracker
        assert app._dialogue_agent is not None

        # OutputRouter depends on DialogueAgent
        assert app._output_router is not None
        assert app._output_router._dialogue_agent is app._dialogue_agent

    @pytest.mark.asyncio
    async def test_start_creates_database_tables(self):
        """Test that start creates database tables."""
        app = Application(db_path=":memory:")
        await app.start()

        # Try to query tables - should not raise error
        async with app._storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cursor:
            tables = [row[0] for row in await cursor.fetchall()]
            assert len(tables) > 0

    @pytest.mark.asyncio
    async def test_start_registers_agents(self):
        """Test that start registers processing agents."""
        app = Application(db_path=":memory:")
        await app.start()

        # EchoAgent should be registered
        agents = app._processing_layer._agents
        assert len(agents) >= 1
        assert "echo_agent" in agents


class TestApplicationStop:
    """Tests for Application.stop()."""

    @pytest.mark.asyncio
    async def test_stop_clears_components(self):
        """Test that stop stops components in reverse order."""
        app = Application(db_path=":memory:")
        await app.start()
        await app.stop()

        # Storage connection should be closed
        assert app._storage._conn is None

    @pytest.mark.asyncio
    async def test_stop_in_reverse_order(self):
        """Test that stop calls components in reverse order."""
        app = Application(db_path=":memory:")
        await app.start()

        # Just verify it doesn't raise errors
        await app.stop()


class TestApplicationReset:
    """Tests for Application.reset()."""

    @pytest.mark.asyncio
    async def test_reset_clears_storage(self):
        """Test that reset clears storage data."""
        app = Application(db_path=":memory:")
        await app.start()

        # Add some data
        await app._dialogue_agent.handle_message("user1", "Hello")

        # Reset
        await app.reset()

        # Verify storage is cleared
        messages = await app._storage.get_messages(
            app._dialogue_agent._dialogue_ids["user1"]
        )
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_reset_restarts_components(self):
        """Test that reset restarts components."""
        app = Application(db_path=":memory:")
        await app.start()

        # Send a message
        response = await app._dialogue_agent.handle_message("user1", "Hello")
        assert response is not None

        # Reset
        await app.reset()

        # Components should still work
        response2 = await app._dialogue_agent.handle_message("user2", "Hi")
        assert response2 is not None

    @pytest.mark.asyncio
    async def test_reset_clears_dialogue_states(self):
        """Test that reset clears dialogue states."""
        app = Application(db_path=":memory:")
        await app.start()

        # Create dialogue state
        await app._dialogue_agent.handle_message("user1", "Hello")

        # Reset
        await app.reset()

        # Dialogue state should be cleared
        state = await app._storage.get_dialogue_state("user1")
        assert state is None


class TestApplicationProperties:
    """Tests for Application properties."""

    @pytest.mark.asyncio
    async def test_storage_property(self):
        """Test storage property."""
        app = Application(db_path=":memory:")
        await app.start()

        storage = app.storage
        assert storage is app._storage

    @pytest.mark.asyncio
    async def test_storage_property_raises_when_not_started(self):
        """Test that storage property raises when not started."""
        app = Application(db_path=":memory:")

        with pytest.raises(RuntimeError, match="not started"):
            _ = app.storage

    @pytest.mark.asyncio
    async def test_dialogue_agent_property(self):
        """Test dialogue_agent property."""
        app = Application(db_path=":memory:")
        await app.start()

        agent = app.dialogue_agent
        assert agent is app._dialogue_agent

    @pytest.mark.asyncio
    async def test_dialogue_agent_property_raises_when_not_started(self):
        """Test that dialogue_agent property raises when not started."""
        app = Application(db_path=":memory:")

        with pytest.raises(RuntimeError, match="not started"):
            _ = app.dialogue_agent

    @pytest.mark.asyncio
    async def test_processing_layer_property(self):
        """Test processing_layer property."""
        app = Application(db_path=":memory:")
        await app.start()

        layer = app.processing_layer
        assert layer is app._processing_layer

    @pytest.mark.asyncio
    async def test_processing_layer_property_raises_when_not_started(self):
        """Test that processing_layer property raises when not started."""
        app = Application(db_path=":memory:")

        with pytest.raises(RuntimeError, match="not started"):
            _ = app.processing_layer
