# Доработка сквозного скелета по результатам ревизии (Review 04)

## Что нужно сделать

Исправить все критические и важные проблемы, найденные при ревизии
задачи 001. Полный список — в `01_tasks/001_skeleton/review_04.md`.

Приоритет: сначала критические (система не запускается),
затем важные, затем замечания.

## Зачем

Сквозной скелет не запускается из-за сломанных импортов, ошибки в SQL-схеме
и отсутствующего импорта. Без исправлений невозможно валидировать архитектуру
и переходить к Iteration 2.

## Acceptance Criteria

- [ ] AC-1: .gitignore корректно настроен (см. блок ниже)
- [ ] AC-2: Приложение запускается без ошибок (`python -m core.app` или `python main.py`)
- [ ] AC-3: Все импорты корректны, нет ImportError
- [ ] AC-4: SQL-схема инициализируется без ошибок
- [ ] AC-5: Тесты запускаются (`pytest`) — не обязательно все зелёные, но нет SyntaxError/ImportError
- [ ] AC-6: VS UI запускается (`npm run dev` из `02_src/vs_ui/`)
- [ ] AC-7: Пути к `03_data/` и `04_logs/` работают независимо от CWD
- [ ] AC-8: EchoAgent записывает TraceEvents `processing_started` / `processing_completed`
- [ ] AC-9: Единственная точка входа — `02_src/main.py`
- [ ] AC-10: `.env.example` создан с описанием переменных (без реальных значений)

## Контекст

### Полный review: `01_tasks/001_skeleton/review_04.md`

### Блок 1: .gitignore (I-1)

Добавить в `.gitignore` в корне проекта:

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

Также создать `02_src/.env.example`:
```
# Anthropic API
ANTHROPIC_API_KEY=your-key-here

# Database
DATABASE_URL=03_data/team_assistant.db
```

### Блок 2: Критические — сломанные импорты sim (C-2, C-3, C-4)

**Проблема:** `core/app.py`, `core/app_patch.py`, `core/api/app.py` содержат
`from .sim import ISim, Sim` — но пакет `sim` находится в `02_src/sim/`,
а не внутри `02_src/core/`.

**Решение:**
- В `core/app.py`: убрать тройной дублированный импорт (строки 7, 8, 15).
  SIM не является частью Core — он подключается извне. Application должен
  получать SIM через dependency injection (передача в конструктор или setter),
  а не импортировать напрямую.
- В `core/app_patch.py`: аналогично убрать импорт sim.
- В `core/api/app.py`: убрать попытку создания SIM (строки 60-63).
  SIM создаётся в `main.py` и передаётся через `control.set_sim_instance()`.

**Принцип:** Core не зависит от SIM. SIM зависит от Core (через HTTP API).
Внутри Core достаточно интерфейса (Protocol) для управления SIM через Control API.

### Блок 3: Отсутствующий import (C-5)

**Файл:** `02_src/core/logging_config.py`, строка 91
**Проблема:** `logging.config.dictConfig()` без `import logging.config`
**Решение:** Добавить `import logging.config` в начало файла.

### Блок 4: SQL-схема — индексы до таблиц (C-6)

**Файл:** `02_src/core/storage/schema.sql`
**Проблема:** `CREATE INDEX` (строки 10-16) стоят перед `CREATE TABLE` (строки 26+).
**Решение:** Переместить все `CREATE INDEX` после соответствующих `CREATE TABLE`.

### Блок 5: Пути к 03_data и 04_logs (I-2)

**Проблема:** Относительные пути `03_data/...` и `04_logs/...` работают
только при запуске из корня проекта.

**Решение:** Определить PROJECT_ROOT в одном месте и строить абсолютные пути.

```python
# 02_src/core/config.py (создать новый файл)
from pathlib import Path

# PROJECT_ROOT = родитель 02_src/ = корень проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "03_data"
LOGS_DIR = PROJECT_ROOT / "04_logs"
DEFAULT_DB_PATH = DATA_DIR / "team_assistant.db"
DEFAULT_LOG_PATH = LOGS_DIR / "app.log"
```

Обновить файлы, использующие хардкод путей:
- `02_src/core/app.py:42` → использовать `DEFAULT_DB_PATH`
- `02_src/core/storage/storage.py:106` → использовать `DEFAULT_DB_PATH`
- `02_src/core/logging_config.py:55` → использовать `DEFAULT_LOG_PATH`

Также обеспечить автоматическое создание папок `03_data/` и `04_logs/`
при запуске (если не существуют).

### Блок 6: Фикстуры тестов (I-3, I-4)

**conftest.py:62** — неправильный порядок аргументов DialogueAgent:
```python
# Было (неправильно):
DialogueAgent(storage, event_bus, tracker, mock_llm)
# Нужно:
DialogueAgent(llm_provider=mock_llm, event_bus=event_bus, storage=storage, tracker=tracker)
```

**conftest.py:73** — неполная сигнатура ProcessingLayer:
```python
# Было (неправильно):
ProcessingLayer(storage, event_bus)
# Нужно:
ProcessingLayer(event_bus=event_bus, storage=storage, tracker=tracker, llm_provider=mock_llm)
```

### Блок 7: Несуществующие методы в тестах (I-5, I-6)

- `test_event_bus.py:151` — вызов `storage.get_bus_messages()`, метода нет в Storage.
  Решение: добавить `get_bus_messages()` в Storage (простой SELECT из bus_messages).

- `test_tracker.py:91,121,149` — вызов `tracker.stop()`, метода нет.
  Решение: добавить `stop()` в Tracker (для симметрии с `start()`).

### Блок 8: Тесты LLMProvider — неправильный путь мока (I-7)

**Файл:** `02_src/tests/test_llm_provider.py`
**Проблема:** Патчат `core.llm.provider.Anthropic`, но модуль называется
`core.llm.llm_provider` и использует `AsyncAnthropic`.
**Решение:** Исправить на `core.llm.llm_provider.anthropic.AsyncAnthropic`
или использовать корректную стратегию мокирования async-клиента.

### Блок 9: Дублирование префикса маршрутов SIM (I-8)

**Файл:** `02_src/core/api/routes/control.py:47,61`
**Проблема:** Роутер с `prefix="/api/control"` + маршрут `"/api/control/sim/start"` = двойной префикс.
**Решение:** Заменить на `"/sim/start"` и `"/sim/stop"`.

### Блок 10: EchoAgent не пишет TraceEvents (I-9, I-12)

**Файл:** `02_src/core/processing/agents/echo_agent.py`
**Проблема:** Нет зависимости на Tracker, использует `print()` вместо `tracker.track()`.
Нарушает AC-8 из task_brief_01.

**Решение:**
- Добавить `tracker: ITracker` в конструктор EchoAgent
- Вызывать `await self.tracker.track("processing_started", f"agent:{self.agent_id}", {...})` при начале обработки
- Вызывать `await self.tracker.track("processing_completed", f"agent:{self.agent_id}", {...})` при завершении
- После этого исправления тест `test_integration.py:61-63` (I-12) станет зелёным

### Блок 11: SIM TraceEvents (I-10)

**Файл:** `02_src/sim/sim.py`
**Проблема:** SIM не записывает `sim_started` / `sim_completed`.
**Решение:** SIM работает как внешний клиент (через HTTP). Два варианта:
- Вариант A: Добавить HTTP-эндпоинт для записи произвольных TraceEvents
- Вариант B: SIM вызывает track() напрямую, если запущен в том же процессе (через `main.py`)
- Рекомендация: Вариант B для MVP (проще)

### Блок 12: Vite config — React plugin (I-11)

**Файл:** `02_src/vs_ui/vite.config.ts`
**Решение:**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // ... остальная конфигурация
})
```

### Блок 13: Единая точка входа (N-4)

**Проблема:** Два `main.py` — `02_src/main.py` и `02_src/core/main.py`.
**Решение:** Каноническая точка входа — `02_src/main.py`.
Удалить `02_src/core/main.py` или превратить в re-export.

### Блок 14: Остальные замечания (N-1..N-9)

Исправить по возможности:
- N-1: Отступ в `echo_agent.py:84` (6→8 пробелов)
- N-2: Заменить `print()` на `logger` во всех файлах
- N-3: Читать `DATABASE_URL` из окружения (после создания config.py из Блока 5 это станет единообразным)
- N-5: `DialogueAgent.start()` — восстанавливать `dialogue_id` из `DialogueState`, а не создавать новый UUID
- N-6: `App.tsx` — дедуплицировать events по `event.id`
- N-7: `datetime.utcnow()` → `datetime.now(timezone.utc)`
- N-8: `ProcessingLayer` — относительные импорты (`from ..event_bus`)
- N-9: Тест `test_start_restores_dialogue_state` — связан с N-5, исправится вместе

### Рекомендуемый порядок исправлений

1. .gitignore + .env.example (Блок 1)
2. config.py с PROJECT_ROOT (Блок 5) — разблокирует пути
3. SQL-схема (Блок 4) — разблокирует Storage
4. import logging.config (Блок 3)
5. Импорты sim (Блок 2) + единая точка входа (Блок 13)
6. EchoAgent + Tracker (Блок 10)
7. Маршруты SIM (Блок 9)
8. Фикстуры тестов (Блок 6)
9. Недостающие методы (Блок 7)
10. Тесты LLMProvider (Блок 8)
11. SIM TraceEvents (Блок 11)
12. Vite config (Блок 12)
13. Остальные замечания (Блок 14)

После всех исправлений: запустить `pytest`, убедиться что тесты проходят,
запустить приложение, убедиться что SIM → Core → VS UI работает end-to-end.
