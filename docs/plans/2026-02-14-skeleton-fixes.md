# Skeleton Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix Review 04 critical/important issues and N-block improvements to restore a runnable skeleton without architectural changes.

**Architecture:** Core remains independent of SIM. SIM is created in `02_src/main.py` and integrated via control router. Paths and logging are centralized in `core/config.py`.

**Tech Stack:** Python (FastAPI, aiosqlite), Node (Vite + React).

---

### Task 1: Create Python venv and install deps

**Files:**
- Modify: none
- Test: none

**Step 1: Create venv**

Run: `python -m venv .venv`
Expected: `.venv/` created.

**Step 2: Activate venv**

Run (PowerShell): `. .venv\Scripts\Activate.ps1`
Expected: prompt shows venv active.

**Step 3: Install Python deps**

Run: `pip install -r 02_src\requirements.txt`
Expected: packages installed.

**Step 4: Commit**

Skip commit (no repo changes).

### Task 2: Repo hygiene (.gitignore + .env.example)

**Files:**
- Modify: `.gitignore`
- Create: `02_src/.env.example`

**Step 1: Update .gitignore**

Add:
```gitignore
# Python
venv/
.venv/
env/
__pycache__/
*.pyc
*.pyo

# Node.js
node_modules/

# Environment (секреты)
.env
**/.env

# SQLite databases
*.db
*.sqlite
*.sqlite3

# Logs
*.log

# Build artifacts
dist/
build/

# Data and logs directories (runtime content)
03_data/
04_logs/
```

**Step 2: Create .env.example**

Create `02_src/.env.example`:
```env
# Anthropic API
ANTHROPIC_API_KEY=your-key-here

# Database
DATABASE_URL=03_data/team_assistant.db
```

**Step 3: Run quick sanity check**

Run: `git status -sb`
Expected: `.gitignore` modified, `.env.example` added.

**Step 4: Commit**

Run:
```bash
git add .gitignore 02_src/.env.example
git commit -m "chore: ignore env and add env example"
```

### Task 3: Add core/config.py and CWD-independent paths

**Files:**
- Create: `02_src/core/config.py`
- Modify: `02_src/core/app.py`, `02_src/core/storage/storage.py`, `02_src/core/logging_config.py`

**Step 1: Add config module**

Create `02_src/core/config.py`:
```python
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "03_data"
LOGS_DIR = PROJECT_ROOT / "04_logs"
DEFAULT_DB_PATH = DATA_DIR / "team_assistant.db"
DEFAULT_LOG_PATH = LOGS_DIR / "app.log"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_db_path(env_value: str | None = None) -> Path:
    if not env_value:
        return DEFAULT_DB_PATH
    candidate = Path(env_value)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
```

**Step 2: Use config in Application**

In `02_src/core/app.py` set default:
```python
from .config import resolve_db_path

class Application:
    def __init__(self, db_path: str | None = None):
        self._db_path = resolve_db_path(db_path)
```

**Step 3: Use config in Storage**

In `02_src/core/storage/storage.py`:
```python
from ..config import resolve_db_path

class Storage:
    def __init__(self, db_path: str | Path | None = None):
        self._db_path = resolve_db_path(str(db_path)) if db_path else resolve_db_path()
```

**Step 4: Use config in logging**

In `02_src/core/logging_config.py`:
```python
from .config import DEFAULT_LOG_PATH

if log_file is None:
    log_file = str(DEFAULT_LOG_PATH)
```

**Step 5: Run focused test**

Run: `python -m core.app`
Expected: no ImportError and logs directory created.

**Step 6: Commit**

Run:
```bash
git add 02_src/core/config.py 02_src/core/app.py 02_src/core/storage/storage.py 02_src/core/logging_config.py
git commit -m "feat: add core config with absolute paths"
```

### Task 4: Fix logging import and UTC timestamp

**Files:**
- Modify: `02_src/core/logging_config.py`

**Step 1: Update imports and timestamp**

Change:
```python
from datetime import datetime
```
To:
```python
from datetime import datetime, timezone
import logging.config
```

Change timestamp:
```python
"timestamp": datetime.now(timezone.utc).isoformat()
```

**Step 2: Run lint-free smoke**

Run: `python -m core.app`
Expected: no AttributeError on logging.config.

**Step 3: Commit**

Run:
```bash
git add 02_src/core/logging_config.py
git commit -m "fix: logging config import and utc timestamp"
```

### Task 5: Fix SQL schema index order

**Files:**
- Modify: `02_src/core/storage/schema.sql`

**Step 1: Move CREATE INDEX after tables**

Place all `CREATE INDEX` statements after related `CREATE TABLE` statements.

**Step 2: Run schema init**

Run: `python -m core.app`
Expected: schema executes without error.

**Step 3: Commit**

Run:
```bash
git add 02_src/core/storage/schema.sql
git commit -m "fix: move indexes after tables"
```

### Task 6: Remove SIM imports from Core, single entrypoint

**Files:**
- Modify: `02_src/core/app.py`, `02_src/core/app_patch.py`, `02_src/core/api/app.py`
- Delete: `02_src/core/main.py`

**Step 1: Remove sim imports from Core**

- Delete `from .sim import ISim, Sim` lines in `core/app.py`.
- Remove SIM creation in `core/app_patch.py` or make it a no-op.
- Remove SIM creation in `core/api/app.py`.

**Step 2: Delete core/main.py**

Remove `02_src/core/main.py` (AC-9).

**Step 3: Smoke run**

Run: `python main.py`
Expected: app starts without ImportError.

**Step 4: Commit**

Run:
```bash
git add 02_src/core/app.py 02_src/core/app_patch.py 02_src/core/api/app.py
git rm 02_src/core/main.py
git commit -m "fix: remove sim imports from core and drop core/main"
```

### Task 7: EchoAgent TraceEvents + logger

**Files:**
- Modify: `02_src/core/processing/agents/echo_agent.py`, `02_src/core/app.py`

**Step 1: Inject tracker into EchoAgent**

Update constructor:
```python
from ...tracker import ITracker

class EchoAgent:
    def __init__(..., tracker: ITracker):
        self._tracker = tracker
```

Update Application registration:
```python
echo_agent = EchoAgent(..., tracker=self._tracker)
```

**Step 2: Emit TraceEvents**

On start of `_handle_input`:
```python
await self._tracker.track(
    "processing_started",
    f"agent:{self._agent_id}",
    {"dialogue_id": dialogue_id, "message_count": len(messages)},
)
```

On completion:
```python
await self._tracker.track(
    "processing_completed",
    f"agent:{self._agent_id}",
    {"dialogue_id": dialogue_id, "output": output},
)
```

Replace `print` with logger calls.

**Step 3: Run existing tests**

Run: `pytest 02_src\tests\test_integration.py -v`
Expected: no TraceEvent assertions failing.

**Step 4: Commit**

Run:
```bash
git add 02_src/core/processing/agents/echo_agent.py 02_src/core/app.py
git commit -m "feat: echo agent trace events"
```

### Task 8: Tracker.stop + Storage.get_bus_messages

**Files:**
- Modify: `02_src/core/tracker/tracker.py`, `02_src/core/storage/storage.py`

**Step 1: Add Tracker.stop (no-op)**

```python
async def stop(self) -> None:
    return
```

**Step 2: Add Storage.get_bus_messages**

Implement SELECT from `bus_messages` returning `BusMessage` list.

**Step 3: Run targeted tests**

Run:
- `pytest 02_src\tests\test_tracker.py -v`
- `pytest 02_src\tests\test_event_bus.py -v`

Expected: no AttributeError.

**Step 4: Commit**

Run:
```bash
git add 02_src/core/tracker/tracker.py 02_src/core/storage/storage.py
git commit -m "feat: add tracker.stop and storage.get_bus_messages"
```

### Task 9: Control routes prefix fix

**Files:**
- Modify: `02_src/core/api/routes/control.py`

**Step 1: Fix routes**

Change:
```python
@router.post("/api/control/sim/start")
@router.post("/api/control/sim/stop")
```
To:
```python
@router.post("/sim/start")
@router.post("/sim/stop")
```

**Step 2: Smoke test**

Run: `python main.py`
Expected: no route duplication.

**Step 3: Commit**

Run:
```bash
git add 02_src/core/api/routes/control.py
git commit -m "fix: control routes sim prefix"
```

### Task 10: Test fixture and LLM mock fixes

**Files:**
- Modify: `02_src/tests/conftest.py`, `02_src/tests/test_llm_provider.py`

**Step 1: Fix DialogueAgent/ProcessingLayer fixtures**

Use correct signature ordering and named args:
```python
da = DialogueAgent(llm_provider=mock_llm, event_bus=event_bus, storage=storage, tracker=tracker)
pl = ProcessingLayer(event_bus=event_bus, storage=storage, tracker=tracker, llm_provider=mock_llm)
```

**Step 2: Fix LLMProvider patch path**

Patch `core.llm.llm_provider.anthropic.AsyncAnthropic` and use `AsyncMock` for async client.

**Step 3: Run tests**

Run: `pytest 02_src\tests\test_llm_provider.py -v`

**Step 4: Commit**

Run:
```bash
git add 02_src/tests/conftest.py 02_src/tests/test_llm_provider.py
git commit -m "fix: test fixtures and llm mocks"
```

### Task 11: SIM TraceEvents and logger

**Files:**
- Modify: `02_src/sim/sim.py`, `02_src/core/api/app.py`

**Step 1: Add tracker injection in SIM**

Add optional tracker and a setter:
```python
from core.tracker import ITracker

class Sim:
    def __init__(..., tracker: ITracker | None = None):
        self._tracker = tracker

    def set_tracker(self, tracker: ITracker) -> None:
        self._tracker = tracker
```

**Step 2: Emit sim_started/sim_completed**

On scenario start/end:
```python
if self._tracker:
    await self._tracker.track("sim_started", "sim", {...})
```

**Step 3: Wire tracker in lifespan**

In `core/api/app.py` after `application.start()`:
```python
from .routes import control
sim = control.get_sim_instance()
if sim and hasattr(sim, "set_tracker"):
    sim.set_tracker(application._tracker)
```

**Step 4: Replace print with logger**

Use `get_logger(__name__)` in sim.

**Step 5: Commit**

Run:
```bash
git add 02_src/sim/sim.py 02_src/core/api/app.py
git commit -m "feat: sim trace events via tracker"
```

### Task 12: VS UI fixes

**Files:**
- Modify: `02_src/vs_ui/vite.config.ts`, `02_src/vs_ui/src/App.tsx`

**Step 1: Add React plugin**

```ts
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
```

**Step 2: Deduplicate events by id**

Replace append with dedup logic:
```ts
setEvents((prev) => {
  const seen = new Set(prev.map((e) => e.id));
  const merged = [...newEvents.filter((e) => !seen.has(e.id)), ...prev];
  return merged;
});
```

**Step 3: Commit**

Run:
```bash
git add 02_src/vs_ui/vite.config.ts 02_src/vs_ui/src/App.tsx
git commit -m "fix: vs ui react plugin and dedup events"
```

### Task 13: N-block cleanup

**Files:**
- Modify: `02_src/core/event_bus/event_bus.py`, `02_src/core/processing/layer.py`, `02_src/core/dialogue/agent.py`

**Step 1: Replace print with logger**

Use `get_logger(__name__)` and log exceptions in EventBus.

**Step 2: ProcessingLayer relative imports**

Change `from core.*` to `from ..*` as needed.

**Step 3: Restore dialogue_id in DialogueAgent.start**

Load `DialogueState` and set `_dialogue_ids[user_id] = state.dialogue_id` if present.

**Step 4: Run targeted tests**

Run: `pytest 02_src\tests\test_dialogue_agent.py::test_start_restores_dialogue_state -v`

**Step 5: Commit**

Run:
```bash
git add 02_src/core/event_bus/event_bus.py 02_src/core/processing/layer.py 02_src/core/dialogue/agent.py
git commit -m "fix: n-block cleanup"
```

### Task 14: Full verification

**Files:**
- Modify: none

**Step 1: Run pytest**

Run: `pytest`
Expected: no SyntaxError/ImportError.

**Step 2: Run app**

Run: `python main.py`
Expected: app starts.

**Step 3: Run VS UI**

Run:
```bash
cd 02_src\vs_ui
npm install
npm run dev
```
Expected: Vite dev server starts.

**Step 4: Commit**

Skip commit (no repo changes).
