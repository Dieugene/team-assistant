"""SQLite storage implementation."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import aiosqlite

from ..config import resolve_db_path
from ..models import (
    AgentState,
    Attachment,
    BusMessage,
    DialogueState,
    Message,
    Team,
    TraceEvent,
    Topic,
    User,
)


class IStorage(Protocol):
    """Persistent storage for all system data (SQLite)."""

    async def init(self) -> None:
        """Initialize database and create tables."""
        ...

    async def close(self) -> None:
        """Close database connection."""
        ...

    # Messages
    async def save_message(self, message: Message) -> None:
        """Save a message to storage."""
        ...

    async def get_messages(
        self, dialogue_id: str, after: datetime | None = None
    ) -> list[Message]:
        """Get messages for a dialogue, optionally after a timestamp."""
        ...

    # DialogueState
    async def save_dialogue_state(self, state: DialogueState) -> None:
        """Save dialogue state."""
        ...

    async def get_dialogue_state(self, user_id: str) -> DialogueState | None:
        """Get dialogue state for a user."""
        ...

    # AgentState
    async def save_agent_state(self, agent_id: str, state: AgentState) -> None:
        """Save agent state."""
        ...

    async def get_agent_state(self, agent_id: str) -> AgentState | None:
        """Get agent state."""
        ...

    # TraceEvents
    async def save_trace_event(self, event: TraceEvent) -> None:
        """Save a trace event."""
        ...

    async def get_trace_events(
        self,
        after: datetime | None = None,
        event_types: list[str] | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[TraceEvent]:
        """Get trace events with optional filters."""
        ...

    # BusMessages
    async def save_bus_message(self, message: BusMessage) -> None:
        """Save a bus message."""
        ...

    async def get_bus_messages(self, limit: int = 100) -> list[BusMessage]:
        """Get bus messages (newest first)."""
        ...

    # Users / Teams
    async def save_team(self, team: Team) -> None:
        """Save a team."""
        ...

    async def save_user(self, user: User) -> None:
        """Save a user."""
        ...

    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        ...

    # Lifecycle
    async def clear(self) -> None:
        """Clear all data."""
        ...


class Storage:
    """SQLite storage implementation."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            self._db_path = resolve_db_path()
        else:
            self._db_path = resolve_db_path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Initialize database and create tables."""
        self._conn = await aiosqlite.connect(self._db_path)

        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        await self._conn.executescript(schema_sql)
        await self._conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    # Messages
    async def save_message(self, message: Message) -> None:
        """Save a message to storage."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        # Generate ID if not provided
        msg_id = message.id or str(uuid.uuid4())

        await self._conn.execute(
            """
            INSERT INTO messages (id, dialogue_id, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                message.dialogue_id,
                message.role,
                message.content,
                message.timestamp,
            ),
        )

        # Save attachments
        for attachment in message.attachments:
            await self._conn.execute(
                """
                INSERT INTO attachments (id, message_id, type, data, url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    attachment.id or str(uuid.uuid4()),
                    msg_id,
                    attachment.type,
                    attachment.data,
                    attachment.url,
                ),
            )

        await self._conn.commit()

    async def get_messages(
        self, dialogue_id: str, after: datetime | None = None
    ) -> list[Message]:
        """Get messages for a dialogue, optionally after a timestamp."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        if after:
            cursor = await self._conn.execute(
                """
                SELECT id, dialogue_id, role, content, timestamp
                FROM messages
                WHERE dialogue_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
                """,
                (dialogue_id, after),
            )
        else:
            cursor = await self._conn.execute(
                """
                SELECT id, dialogue_id, role, content, timestamp
                FROM messages
                WHERE dialogue_id = ?
                ORDER BY timestamp ASC
                """,
                (dialogue_id,),
            )

        rows = await cursor.fetchall()

        messages = []
        for row in rows:
            # Get attachments for this message
            att_cursor = await self._conn.execute(
                """
                SELECT id, type, data, url
                FROM attachments
                WHERE message_id = ?
                """,
                (row[0],),
            )
            att_rows = await att_cursor.fetchall()

            attachments = [
                Attachment(
                    id=att[0],
                    message_id=row[0],
                    type=att[1],
                    data=att[2],
                    url=att[3],
                )
                for att in att_rows
            ]

            # Fix timezone for timestamp
            ts = datetime.fromisoformat(row[4]).replace(tzinfo=timezone.utc)

            messages.append(
                Message(
                    id=row[0],
                    dialogue_id=row[1],
                    role=row[2],
                    content=row[3],
                    timestamp=ts,
                    attachments=attachments,
                )
            )

        return messages

    # DialogueState
    async def save_dialogue_state(self, state: DialogueState) -> None:
        """Save dialogue state."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO dialogue_states
            (user_id, dialogue_id, last_published_timestamp, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (state.user_id, state.dialogue_id, state.last_published_timestamp),
        )
        await self._conn.commit()

    async def get_dialogue_state(self, user_id: str) -> DialogueState | None:
        """Get dialogue state for a user."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        cursor = await self._conn.execute(
            """
            SELECT user_id, dialogue_id, last_published_timestamp
            FROM dialogue_states
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return DialogueState(
            user_id=row[0],
            dialogue_id=row[1],
            last_published_timestamp=(
                datetime.fromisoformat(row[2]).replace(tzinfo=timezone.utc)
                if row[2]
                else None
            ),
        )

    # AgentState
    async def save_agent_state(self, agent_id: str, state: AgentState) -> None:
        """Save agent state."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO agent_states
            (agent_id, data, sgr_traces, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                agent_id,
                json.dumps(state.data),
                json.dumps(state.sgr_traces),
            ),
        )
        await self._conn.commit()

    async def get_agent_state(self, agent_id: str) -> AgentState | None:
        """Get agent state."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        cursor = await self._conn.execute(
            """
            SELECT agent_id, data, sgr_traces
            FROM agent_states
            WHERE agent_id = ?
            """,
            (agent_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return AgentState(
            agent_id=row[0],
            data=json.loads(row[1]),
            sgr_traces=json.loads(row[2]),
        )

    # TraceEvents
    async def save_trace_event(self, event: TraceEvent) -> None:
        """Save a trace event."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        await self._conn.execute(
            """
            INSERT INTO trace_events (id, event_type, actor, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.id or str(uuid.uuid4()),
                event.event_type,
                event.actor,
                json.dumps(event.data),
                event.timestamp,
            ),
        )
        await self._conn.commit()

    async def get_trace_events(
        self,
        after: datetime | None = None,
        event_types: list[str] | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[TraceEvent]:
        """Get trace events with optional filters."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        # Build query dynamically
        conditions = []
        params = []

        if after:
            conditions.append("timestamp > ?")
            params.append(after)
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        if actor:
            conditions.append("actor = ?")
            params.append(actor)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT id, event_type, actor, data, timestamp
            FROM trace_events
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()

        return [
            TraceEvent(
                id=row[0],
                event_type=row[1],
                actor=row[2],
                data=json.loads(row[3]),
                timestamp=datetime.fromisoformat(row[4]).replace(tzinfo=timezone.utc),
            )
            for row in rows
        ]

    # BusMessages
    async def save_bus_message(self, message: BusMessage) -> None:
        """Save a bus message."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        await self._conn.execute(
            """
            INSERT INTO bus_messages (id, topic, payload, source, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message.id or str(uuid.uuid4()),
                message.topic.value,
                json.dumps(message.payload),
                message.source,
                message.timestamp,
            ),
        )
        await self._conn.commit()

    async def get_bus_messages(self, limit: int = 100) -> list[BusMessage]:
        """Get bus messages (newest first)."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, topic, payload, source, timestamp
            FROM bus_messages
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()

        return [
            BusMessage(
                id=row[0],
                topic=Topic(row[1]),
                payload=json.loads(row[2]),
                source=row[3],
                timestamp=datetime.fromisoformat(row[4]).replace(tzinfo=timezone.utc),
            )
            for row in rows
        ]

    # Users / Teams
    async def save_team(self, team: Team) -> None:
        """Save a team."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO teams (id, name)
            VALUES (?, ?)
            """,
            (team.id, team.name),
        )
        await self._conn.commit()

    async def save_user(self, user: User) -> None:
        """Save a user."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO users (id, team_id, name)
            VALUES (?, ?, ?)
            """,
            (user.id, user.team_id, user.name),
        )
        await self._conn.commit()

    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, team_id, name
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return User(id=row[0], team_id=row[1], name=row[2])

    # Lifecycle
    async def clear(self) -> None:
        """Clear all data."""
        if not self._conn:
            raise RuntimeError("Storage not initialized")

        tables = [
            "attachments",
            "messages",
            "dialogue_states",
            "agent_states",
            "trace_events",
            "bus_messages",
            "users",
            "teams",
        ]

        for table in tables:
            await self._conn.execute(f"DELETE FROM {table}")

        await self._conn.commit()
