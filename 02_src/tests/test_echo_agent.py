"""Tests for EchoAgent."""

import pytest

from core.models import BusMessage, Topic
from core.processing.agents.echo_agent import EchoAgent


class TestEchoAgentInit:
    """Tests for EchoAgent initialization."""

    def test_init(self, storage, event_bus, mock_llm):
        """Test creating EchoAgent."""
        agent = EchoAgent(
            agent_id="echo1",
            event_bus=event_bus,
            storage=storage,
            llm_provider=mock_llm,
        )
        assert agent.agent_id == "echo1"


class TestEchoAgentStart:
    """Tests for EchoAgent.start()."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_input(self, storage, event_bus,  mock_llm):
        """Test that start subscribes to INPUT topic."""
        agent = EchoAgent(
            agent_id="echo1",
            event_bus=event_bus,
            storage=storage,
            llm_provider=mock_llm,
        )
        await agent.start()

        # Check subscription
        assert Topic.INPUT in event_bus._subscribers
        handlers = event_bus._subscribers[Topic.INPUT]
        assert len(handlers) >= 1


class TestEchoAgentHandle:
    """Tests for EchoAgent._handle_input()."""

    @pytest.mark.asyncio
    async def test_handle_input_processes_bus_message(
        self, storage, event_bus,  mock_llm
    ):
        """Test that _handle_input processes BusMessage."""
        agent = EchoAgent(
            agent_id="echo1",
            event_bus=event_bus,
            storage=storage,
            llm_provider=mock_llm,
        )
        await agent.start()

        # Publish input message
        ts = datetime.now(timezone.utc)
        input_msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={
                "user_id": "user1",
                "dialogue_id": "dialogue1",
                "messages": [
                    {"id": "msg1", "role": "user", "content": "Hello"},
                    {"id": "msg2", "role": "assistant", "content": "Hi"},
                ],
            },
            source="dialogue_agent",
            timestamp=ts,
        )

        # Track output
        output_published = []

        async def output_handler(msg: BusMessage):
            output_published.append(msg)

        event_bus.subscribe(Topic.OUTPUT, output_handler)
        await event_bus.publish(input_msg)

        # Give time for async processing
        import asyncio

        await asyncio.sleep(0.1)

        # Verify output was published
        assert len(output_published) >= 1
        assert output_published[0].topic == Topic.OUTPUT
        assert "content" in output_published[0].payload

  
    @pytest.mark.asyncio
    async def test_handle_input_generates_echo_output(
        self, storage, event_bus,  mock_llm
    ):
        """Test that _handle_input generates correct echo output."""
        agent = EchoAgent(
            agent_id="echo1",
            event_bus=event_bus,
            storage=storage,
            llm_provider=mock_llm,
        )
        await agent.start()

        ts = datetime.now(timezone.utc)
        input_msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={
                "user_id": "user1",
                "dialogue_id": "dialogue123",
                "messages": [
                    {"id": "msg1", "role": "user", "content": "Test"},
                ],
            },
            source="test",
            timestamp=ts,
        )

        output_published = []

        async def output_handler(msg: BusMessage):
            output_published.append(msg)

        event_bus.subscribe(Topic.OUTPUT, output_handler)
        await event_bus.publish(input_msg)

        import asyncio

        await asyncio.sleep(0.1)

        # Verify output format
        assert len(output_published) >= 1
        output = output_published[0]
        assert "1 messages from dialogue123" in output.payload["content"]

    @pytest.mark.asyncio
    async def test_handle_input_extracts_user_id(
        self, storage, event_bus,  mock_llm
    ):
        """Test that _handle_input extracts user_id from payload."""
        agent = EchoAgent(
            agent_id="echo1",
            event_bus=event_bus,
            storage=storage,
            llm_provider=mock_llm,
        )
        await agent.start()

        ts = datetime.now(timezone.utc)
        input_msg = BusMessage(
            id="bus1",
            topic=Topic.INPUT,
            payload={
                "user_id": "custom_user",
                "dialogue_id": "dialogue1",
                "messages": [],
            },
            source="test",
            timestamp=ts,
        )

        output_published = []

        async def output_handler(msg: BusMessage):
            output_published.append(msg)

        event_bus.subscribe(Topic.OUTPUT, output_handler)
        await event_bus.publish(input_msg)

        import asyncio

        await asyncio.sleep(0.1)

        # Verify user_id in output
        assert len(output_published) >= 1
        assert output_published[0].payload["user_id"] == "custom_user"


# Need to import datetime
from datetime import datetime, timezone
