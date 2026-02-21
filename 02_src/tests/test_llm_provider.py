"""Tests for LLMProvider."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm import LLMProvider


class TestLLMProviderInit:
    """Tests for LLMProvider initialization."""

    def test_init_with_api_key(self, monkeypatch):
        """Test initialization with API key."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        with patch("core.llm.llm_provider.anthropic.AsyncAnthropic"):
            provider = LLMProvider()
            assert provider is not None

    def test_init_without_api_key(self, monkeypatch):
        """Test initialization without API key raises error."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("core.llm.llm_provider.anthropic.AsyncAnthropic"):
            with pytest.raises(Exception):
                LLMProvider()


class TestLLMProviderComplete:
    """Tests for LLMProvider.complete() method."""

    @pytest.mark.asyncio
    async def test_complete_returns_response(self, monkeypatch):
        """Test that complete() returns LLM response."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        # Mock Anthropic client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Test response")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.llm.llm_provider.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = LLMProvider()
            response = await provider.complete(
                messages=[{"role": "user", "content": "Hello"}]
            )

            assert response == "Test response"

    @pytest.mark.asyncio
    async def test_complete_sends_correct_format(self, monkeypatch):
        """Test that complete() sends correct format to API."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Response")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.llm.llm_provider.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = LLMProvider()
            await provider.complete(
                messages=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"},
                ],
                system="You are helpful",
                max_tokens=2048,
            )

            # Verify API was called with correct parameters
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args

            assert call_args.kwargs["model"] == "claude-3-5-sonnet-20241022"
            assert call_args.kwargs["max_tokens"] == 2048
            assert call_args.kwargs["system"] == "You are helpful"
            assert len(call_args.kwargs["messages"]) == 2

    @pytest.mark.asyncio
    async def test_complete_with_default_params(self, monkeypatch):
        """Test complete() with default parameters."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Default response")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.llm.llm_provider.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = LLMProvider()
            response = await provider.complete(
                messages=[{"role": "user", "content": "Test"}]
            )

            assert response == "Default response"
            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["max_tokens"] == 1024  # default

    @pytest.mark.asyncio
    async def test_complete_propagates_errors(self, monkeypatch):
        """Test that API errors are propagated."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        mock_client = Mock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch(
            "core.llm.llm_provider.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = LLMProvider()

            with pytest.raises(Exception, match="API Error"):
                await provider.complete(
                    messages=[{"role": "user", "content": "Test"}]
                )

    @pytest.mark.asyncio
    async def test_complete_empty_messages(self, monkeypatch):
        """Test complete() with empty messages list."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "core.llm.llm_provider.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = LLMProvider()
            response = await provider.complete(messages=[])

            assert response == ""
