-- SQLite schema for Team Assistant Core

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    dialogue_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Attachments
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    type TEXT NOT NULL,
    data BLOB,
    url TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- DialogueState
CREATE TABLE IF NOT EXISTS dialogue_states (
    user_id TEXT PRIMARY KEY,
    dialogue_id TEXT NOT NULL,
    last_published_timestamp TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AgentState
CREATE TABLE IF NOT EXISTS agent_states (
    agent_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,  -- JSON dump of dict
    sgr_traces TEXT NOT NULL,  -- JSON dump of list[dict]
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TraceEvents
CREATE TABLE IF NOT EXISTS trace_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON dump
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BusMessages
CREATE TABLE IF NOT EXISTS bus_messages (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL CHECK(topic IN ('input', 'processed', 'output')),
    payload TEXT NOT NULL,  -- JSON dump
    source TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_dialogue_id ON messages(dialogue_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_trace_events_timestamp ON trace_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_trace_events_event_type ON trace_events(event_type);
CREATE INDEX IF NOT EXISTS idx_trace_events_actor ON trace_events(actor);
CREATE INDEX IF NOT EXISTS idx_bus_messages_topic ON bus_messages(topic);
