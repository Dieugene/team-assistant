"""SIM implementation - hardcoded scenario for testing."""

import asyncio
import random
from typing import Protocol

import httpx

from core.logging_config import get_logger
from core.tracker import ITracker

logger = get_logger(__name__)

class ISim(Protocol):
    """Generate test data. In Iteration 1: hardcoded scenario."""

    async def start(self) -> None:
        """Start hardcoded scenario."""
        ...

    async def stop(self) -> None:
        """Stop scenario."""
        ...


class Sim:
    """SIM with hardcoded scenario for testing."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        tracker: ITracker | None = None,
    ):
        self._api_url = api_url
        self._tracker = tracker
        self._running = False
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    def set_tracker(self, tracker: ITracker) -> None:
        """Inject tracker for SIM trace events."""
        self._tracker = tracker

    async def start(self) -> None:
        """Start hardcoded scenario."""
        if self._running:
            return

        self._running = True
        self._client = httpx.AsyncClient()

        # Start background task
        self._task = asyncio.create_task(self._run_scenario())

    async def stop(self) -> None:
        """Stop scenario."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.aclose()

    async def _run_scenario(self) -> None:
        """Run hardcoded scenario."""
        # Define virtual users
        virtual_users = [
            {"user_id": "user_001", "name": "Alice"},
            {"user_id": "user_002", "name": "Bob"},
            {"user_id": "user_003", "name": "Charlie"},
        ]

        # Define messages for each user
        messages_per_user = [
            ["Привет! Как дела?", "Помоги с задачей", "Спасибо за помощь!"],
            ["Привет всем", "У меня есть вопрос", "Понял, спасибо"],
            ["Добрый день", "Мне нужна помощь", "Отлично, разобрался"],
        ]

        try:
            if self._tracker:
                await self._tracker.track(
                    "sim_started",
                    "sim",
                    {
                        "scenario": "hardcoded",
                        "user_count": len(virtual_users),
                        "message_count": sum(len(m) for m in messages_per_user),
                    },
                )

            # Send messages with delays
            for i in range(3):  # 3 rounds of messages
                if not self._running:
                    break

                for user_idx, user in enumerate(virtual_users):
                    if not self._running:
                        break

                    if i < len(messages_per_user[user_idx]):
                        message_text = messages_per_user[user_idx][i]

                        # Send message
                        await self._send_message(user["user_id"], message_text)

                        # Random delay between messages (1-3 seconds)
                        await asyncio.sleep(random.uniform(1, 3))

                # Small delay between rounds
                await asyncio.sleep(2)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("SIM scenario error: %s", e)
        finally:
            if self._tracker:
                await self._tracker.track(
                    "sim_completed",
                    "sim",
                    {
                        "scenario": "hardcoded",
                        "user_count": len(virtual_users),
                        "message_count": sum(len(m) for m in messages_per_user),
                    },
                )

    async def _send_message(self, user_id: str, text: str) -> None:
        """Send a message via HTTP API."""
        if not self._client:
            return

        try:
            response = await self._client.post(
                f"{self._api_url}/api/messages",
                json={"user_id": user_id, "text": text},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("SIM: %s -> %s", user_id, text)
                logger.info("SIM: Response: %s", data.get("response", "N/A"))
            else:
                logger.error(
                    "SIM: Error sending message: %s",
                    response.status_code,
                )

        except Exception as e:
            logger.error("SIM: Failed to send message: %s", e)
