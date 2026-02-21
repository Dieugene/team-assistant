# Техническое задание: Сквозной скелет Team Assistant

## 1. Анализ задачи

Реализовать базовую архитектуру системы Team Assistant в минимальной конфигурации. Система должна обеспечивать полный цикл обработки сообщений: от приёма через HTTP API до отображения в веб-интерфейсе.

**Ключевая особенность:** Это end-to-end задача, где все компоненты создаются одновременно и связываются в единый поток. Разделение на подзадачи создаст проблемы интеграции.

## 2. Текущее состояние

Кодовая база пуста (только `.gitkeep` в `02_src/`).

Создаваемая структура директорий:
```
02_src/
├── core/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── messages.py       # Message, Attachment, Team, User
│   │   ├── dialogue.py       # DialogueState
│   │   ├── agents.py         # AgentState, BusMessage
│   │   └── tracing.py       # TraceEvent, Topic
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── schema.sql        # SQLite схема
│   │   └── storage.py        # IStorage implementation
│   ├── event_bus/
│   │   ├── __init__.py
│   │   └── event_bus.py      # IEventBus implementation
│   ├── tracker/
│   │   ├── __init__.py
│   │   └── tracker.py        # ITracker implementation
│   ├── llm/
│   │   ├── __init__.py
│   │   └── llm_provider.py   # ILLMProvider (Claude)
│   ├── dialogue/
│   │   ├── __init__.py
│   │   ├── agent.py          # IDialogueAgent
│   │   └── buffer.py         # DialogueBuffer
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── layer.py          # IProcessingLayer
│   │   └── agents/
│   │       ├── __init__.py
│   │       └── echo_agent.py  # Echo ProcessingAgent
│   ├── output_router/
│   │   ├── __init__.py
│   │   └── router.py         # IOutputRouter
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py            # FastAPI app
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── messaging.py   # POST /api/messages
│   │       ├── observability.py # GET /api/trace-events
│   │       └── control.py    # POST /api/control/*
│   └── app.py               # IApplication (bootstrap)
├── sim/
│   ├── __init__.py
│   └── sim.py               # ISim (hardcoded)
└── vs_ui/
    └── src/
        ├── api/
        │   └── client.ts     # Polling client
        ├── views/
        │   └── Timeline.tsx # Timeline view
        ├── App.tsx
        ├── main.tsx
        └── vite.config.ts
```

## 3. Предлагаемое решение

### 3.1. Общий подход

**Архитектура:** Long-running process на Python asyncio с in-memory EventBus. Все компоненты живут в едином процессе, взаимодействуют через EventBus (пуб/саб) и прямые вызовы.

**Порядок разработки:** Снизу-вверх — от инфраструктурных компонентов (Storage, EventBus) к бизнес-логике (DialogueAgent, ProcessingAgents) и интерфейсам (API, VS UI).

**Тестирование:** Unit-тесты для каждого компонента + один интеграционный тест end-to-end (SIM → Core → VS UI).

### 3.2. Компоненты

#### Models (dataclasses)
- **Назначение:** Типизированные структуры данных для всех сущностей системы
- **Интерфейс:** Классы `@dataclass` с полями согласно task_brief
- **Файлы:**
  - `models/messages.py`: Team, User, Message, Attachment
  - `models/dialogue.py`: DialogueState
  - `models/agents.py`: AgentState, BusMessage, Topic (Enum)
  - `models/tracing.py`: TraceEvent
- **Зависимости:** Нет
- **Детали:**
  - Использовать `dataclasses` стандартной библиотеки
  - Поля с типами `str`, `datetime`, `list`, `dict`, `Literal`
  - `field(default_factory=list)` для mutable defaults

#### Storage
- **Назначение:** SQLite персистентность для всех сущностей
- **Интерфейс:** Реализует `IStorage` из task_brief
- **Зависимости:** aiosqlite, models
- **Ключевые методы:**
  - `init()`: Создаёт таблицы из `schema.sql` если не существуют
  - `save_message()`, `get_messages()`: CRUD для Messages
  - `save_dialogue_state()`, `get_dialogue_state()`: CRUD для DialogueState
  - `save_agent_state()`, `get_agent_state()`: CRUD для AgentState
  - `save_trace_event()`, `get_trace_events()`: CRUD для TraceEvents
  - `save_bus_message()`: Персистентность BusMessages
  - `save_team()`, `save_user()`, `get_user()`: CRUD для Teams/Users
  - `clear()`: Удаляет все данные (для reset между тестами)
- **Детали:**
  - Использовать `aiosqlite` для async операций
  - `schema.sql`: CREATE TABLE с индексами по часто запрашиваемым полям (dialogue_id, user_id, timestamp)
  - При вставке генерировать UUID если не передан
  - `get_trace_events()` поддерживает фильтрацию по `after`, `event_types`, `actor`, `limit`
  - Использовать параметризованные запросы для защиты от SQL injection

#### EventBus
- **Назначение:** In-memory pub/sub для BusMessages между компонентами
- **Интерфейс:** Реализует `IEventBus` из task_brief
- **Зависимости:** Storage (для персистентности BusMessages), models
- **Ключевые методы:**
  - `subscribe(topic, handler)`: Регистрирует callback для Topic
  - `publish(message)`: Асинхронно вызывает всех подписчиков Topic, сохраняет в Storage
- **Детали:**
  - Внутри: `dict[Topic, list[Handler]]` для подписчиков
  - При publish: найти всех подписчиков topic, вызвать асинхронно через `asyncio.gather()`
  - Обработка ошибок: логировать ошибки в callback, но не прерывать других подписчиков
  - После вызова подписчиков: `storage.save_bus_message(message)`
  - Использовать `asyncio.Queue` если нужна сериализация (опционально для MVP)

#### Tracker
- **Назначение:** Запись TraceEvents через два канала (подписка + прямые вызовы)
- **Интерфейс:** Реализует `ITracker` из task_brief
- **Зависимости:** EventBus, Storage, models
- **Ключевые методы:**
  - `track(event_type, actor, data)`: Создаёт TraceEvent и сохраняет в Storage
  - `start()`: Подписывается на все Topics EventBus
- **Детали:**
  - При подписке на EventBus: на каждый BusMessage создавать `TraceEvent` с типом "bus_message_published"
  - В callback: извлечь topic, source, payload summary (первые 100 символов)
  - Генерировать UUID для TraceEvent.id
  - Использовать `datetime.now(timezone.utc)` для timestamp

#### LLMProvider
- **Назначение:** Абстракция над Anthropic Claude API
- **Интерфейс:** Реализует `ILLMProvider` из task_brief
- **Зависимости:** anthropic (библиотека)
- **Ключевые методы:**
  - `complete(messages, system, max_tokens)`: Отправляет запрос в Claude, возвращает текст
- **Детали:**
  - Использовать `anthropic.AsyncAnthropic` клиент
  - Прокидывать API key через переменную окружения `ANTHROPIC_API_KEY`
  - Модель: `claude-3-5-sonnet-20241022` (или актуальную на момент реализации)
  - Преобразовывать формат messages из [{"role", "content"}] в формат Anthropic
  - Обрабатывать ошибки API и пробрасывать исключения

#### DialogueBuffer
- **Назначение:** Вычисляемый подмассив Messages, накапливаемых для публикации
- **Интерфейс:** Внутренний класс DialogueAgent
- **Зависимости:** models
- **Ключевые методы:**
  - `add(message)`: Добавляет Message в буфер
  - `get_unpublished()`: Возвращает список Messages после last_published_timestamp
  - `get_all()`: Возвращает все Messages в буфере
  - `clear()`: Очищает буфер
- **Детали:**
  - Буфер — это просто список Messages в памяти (хранится в DialogueAgent)
  - `get_unpublished()` фильтрует по `message.timestamp > dialogue_state.last_published_timestamp`

#### DialogueAgent
- **Назначение:** Управление диалогами, приём/ответ Messages, буферизация, публикация
- **Интерфейс:** Реализует `IDialogueAgent` из task_brief
- **Зависимости:** LLMProvider, EventBus, Storage, Tracker, models
- **Ключевые методы:**
  - `handle_message(user_id, text)`: Основной метод обработки
  - `deliver_output(user_id, content)`: Доставка output от OutputRouter
  - `start()`: Восстанавливает DialogueState из Storage
  - `stop()`: Сохраняет DialogueState
- **Логика `handle_message`:**
  1. Получить или создать `DialogueState` для user_id
  2. Создать `Message(role="user", content=text)`, сохранить через `storage.save_message()`
  3. Вызвать `tracker.track("message_received", "dialogue_agent", {user_id, dialogue_id, message_text})`
  4. Получить контекст диалога: `storage.get_messages(dialogue_id)` → список messages
  5. Вызвать `llm.complete(messages)` → получить ответ
  6. Создать `Message(role="assistant", content=response)`, сохранить
  7. Вызвать `tracker.track("message_responded", "dialogue_agent", {user_id, dialogue_id, response_text})`
  8. Добавить оба сообщения в буфер
  9. Вернуть response текст
- **Логика буферизации:**
  - Фоновая задача (`asyncio.create_task`): каждые 5 секунд проверять буфер
  - Если есть неопубликованные messages → создать `BusMessage(topic=INPUT, payload={messages})`
  - Опубликовать через `event_bus.publish()`
  - Обновить `dialogue_state.last_published_timestamp`
  - Вызвать `tracker.track("buffer_published", "dialogue_agent", {...})`
- **Детали:**
  - Хранить `dict[user_id, list[Message]]` для буферов в памяти
  - При старте загрузить `DialogueState` из Storage для активных пользователей
  - `deliver_output`: создать `Message(role="system")`, сохранить, записать TraceEvent

#### ProcessingAgent (Echo)
- **Назначение:** Минимальный агент для проверки потока данных
- **Интерфейс:** Реализует `IProcessingAgent` из task_brief
- **Зависимости:** EventBus, Tracker, LLMProvider, Storage
- **Ключевые методы:**
  - `agent_id`: "echo_agent"
  - `start()`: Подписывается на EventBus topic=INPUT
  - `stop()`: Отписывается
  - `_handle_input(bus_message)`: Callback для входящих BusMessages
- **Логика `_handle_input`:**
  1. Вызвать `tracker.track("processing_started", "echo_agent", {agent_id, input_summary})`
  2. Извлечь payload из BusMessage (список messages)
  3. Сформировать output: `"Echo: {len(messages)} messages from {dialogue_id}"`
  4. Создать `BusMessage(topic=OUTPUT, payload={content: output, user_id: ...})`
  5. Опубликовать в EventBus
  6. Вызвать `tracker.track("processing_completed", "echo_agent", {agent_id, output_summary})`
- **Детали:**
  - Не использовать AgentState в MVP (echo не хранит контекст)
  - Извлекать user_id из payload входящего BusMessage

#### ProcessingLayer
- **Назначение:** Управление жизненным циклом ProcessingAgents
- **Интерфейс:** Реализует `IProcessingLayer` из task_brief
- **Зависимости:** EventBus, Storage, LLMProvider, Tracker
- **Ключевые методы:**
  - `register_agent(agent)`: Регистрирует агент
  - `start()`: Вызывает `agent.start()` для всех зарегистрированных
  - `stop()`: Вызывает `agent.stop()` для всех
- **Детали:**
  - Хранить `list[IProcessingAgent]` зарегистрированных агентов
  - При регистрации передать агентам ссылки на EventBus, Storage, Tracker, LLMProvider
  - В `main()`: создать EchoAgent и зарегистрировать в ProcessingLayer

#### OutputRouter
- **Назначение:** Предобработка output перед доставкой (в MVP — passthrough)
- **Интерфейс:** Реализует `IOutputRouter` из task_brief
- **Зависимости:** EventBus, DialogueAgent, Tracker
- **Ключевые методы:**
  - `start()`: Подписывается на EventBus topic=OUTPUT
  - `stop()`: Отписывается
  - `_handle_output(bus_message)`: Callback для BusMessages
- **Логика `_handle_output` (MVP — passthrough):**
  1. Извлечь payload: `{user_id, content}`
  2. Вызвать `tracker.track("output_routed", "output_router", {target_user_id, content_summary})`
  3. Вызвать `dialogue_agent.deliver_output(user_id, content)`
- **Детали:**
  - В MVP без адресации/агрегации/дедупликации — прямая пересылка

#### HTTP API (FastAPI)
- **Назначение:** REST интерфейс для SIM и VS UI
- **Интерфейс:** Эндпоинты из task_brief
- **Зависимости:** FastAPI, DialogueAgent, Storage, Application, models
- **Эндпоинты:**
  - `POST /api/messages`: Принимает `{user_id, text}`, возвращает `{response}`
  - `GET /api/trace-events`: Возвращает список TraceEvents (с фильтрацией)
  - `POST /api/control/reset`: Вызывает `application.reset()`
  - `POST /api/control/sim/start`: Вызывает `sim.start()`
  - `POST /api/control/sim/stop`: Вызывает `sim.stop()`
- **Детали:**
  - Использовать `pydantic` для валидации request body
  - `GET /api/trace-events`: параметры query string (after, limit, event_type, actor)
  - Возвращать TraceEvents как dict (автоматически сериализуется Pydantic)
  - Все ошибки оборачивать в HTTP 500 с логированием

#### Application (Bootstrap)
- **Назначение:** Инициализация и управление жизненным циклом компонентов
- **Интерфейс:** Реализует `IApplication` из task_brief
- **Зависимости:** Все компоненты
- **Ключевые методы:**
  - `start()`: Инициализация в порядке зависимостей
  - `stop()`: Остановка в обратном порядке
  - `reset()`: Сброс данных между тестами
- **Логика `start`:**
  1. Инициализировать `Storage` (создать/connect БД)
  2. Инициализировать `EventBus` (передать Storage)
  3. Инициализировать `Tracker` (подписаться на EventBus)
  4. Инициализировать `LLMProvider` (проверить API key)
  5. Инициализировать `OutputRouter` (подписаться на EventBus topic=OUTPUT)
  6. Инициализировать `ProcessingLayer` (зарегистрировать EchoAgent, запустить)
  7. Инициализировать `DialogueAgent` (восстановить состояния из Storage)
  8. Инициализировать `SIM` (hardcoded сценарий)
  9. Запустить `FastAPI` app
- **Логика `stop`:**
  - Обратный порядок: остановить SIM → DialogueAgent → ProcessingLayer → OutputRouter → LLMProvider → Tracker → EventBus → Storage
- **Логика `reset`:**
  1. Вызвать `dialogue_agent.stop()` (сохранить состояния)
  2. Вызвать `processing_layer.stop()`
  3. Вызвать `storage.clear()` (удалить все данные)
  4. Вызвать `processing_layer.start()` (перезапустить агенты)
  5. Вызвать `dialogue_agent.start()` (восстановить пустые состояния)

#### SIM
- **Назначение:** Генерация тестовых данных (hardcoded сценарий)
- **Интерфейс:** Реализует `ISim` из task_brief
- **Зависимости:** httpx (для HTTP запросов к API)
- **Ключевые методы:**
  - `start()`: Запускает hardcoded сценарий
  - `stop()`: Останавливает сценарий
- **Логика hardcoded сценария:**
  1. Создать 2-3 VirtualUsers с разными user_id
  2. Для каждого VirtualUser: отправить 3-5 сообщений через `POST /api/messages`
  3. Задержки между сообщениями 1-3 секунды (random)
  4. Сообщения: простые тестовые фразы ("Привет", "Как дела?", "Помоги с задачей")
- **Детали:**
  - Использовать `httpx.AsyncClient` для HTTP запросов
  - API URL: `http://localhost:8000` (конфигурируемо)
  - Логировать отправку и получение ответов

#### VS UI (TypeScript/React)
- **Назначение:** Веб-интерфейс для наблюдения (Timeline view)
- **Интерфейс:** React приложение с Vite
- **Зависимости:** React, TypeScript, Vite
- **Компоненты:**
  - `api/client.ts`: Polling клиент для `/api/trace-events`
  - `views/Timeline.tsx`: Отображение TraceEvents хронологически
- **Логика polling:**
  - `setInterval` каждые 2-3 секунды
  - Запрашивать `GET /api/trace-events?after={last_timestamp}&limit=50`
  - Добавлять новые TraceEvents в состояние
  - `last_timestamp` обновлять при получении данных
- **Timeline view:**
  - Отображать TraceEvents в обратном хронологическом порядке (новые сверху)
  - Формат: `[timestamp] {actor}: {event_type} — {data}`
  - Стилизация: серые карточки на белом фоне
- **Детали:**
  - Использовать `useState`, `useEffect` для управления состоянием
  - Типы TypeScript: интерфейс `TraceEvent` с полями из task_brief
  - Vite dev server: `npm run dev` на порту 5173

### 3.3. Структуры данных

**SQLite схема (storage/schema.sql):**

```sql
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
CREATE INDEX idx_messages_dialogue_id ON messages(dialogue_id);
CREATE INDEX idx_messages_timestamp ON messages(timestamp);

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
CREATE INDEX idx_trace_events_timestamp ON trace_events(timestamp);
CREATE INDEX idx_trace_events_event_type ON trace_events(event_type);
CREATE INDEX idx_trace_events_actor ON trace_events(actor);

-- BusMessages
CREATE TABLE IF NOT EXISTS bus_messages (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL CHECK(topic IN ('input', 'processed', 'output')),
    payload TEXT NOT NULL,  -- JSON dump
    source TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_bus_messages_topic ON bus_messages(topic);
```

### 3.4. Ключевые алгоритмы

**Bootstrap последовательность:**
1. Storage: `await init()` → создать таблицы, открыть соединение
2. EventBus: создать экземпляр, передать Storage для персистентности
3. Tracker: создать, подписаться на EventBus (все topics)
4. LLMProvider: создать, проверить `ANTHROPIC_API_KEY`
5. OutputRouter: создать, подписаться на EventBus topic=OUTPUT
6. ProcessingLayer: создать, зарегистрировать EchoAgent, `await start()`
7. DialogueAgent: создать, `await start()` → восстановить DialogueStates
8. SIM: создать (но не запускать)
9. HTTP API: создать FastAPI app, передать DialogueAgent, Storage, Application, SIM

**Поток сообщения от SIM до VS UI:**
1. SIM → `POST /api/messages` → HTTP API handler
2. Handler → `dialogue_agent.handle_message(user_id, text)`
3. DialogueAgent → сохранить user Message → `llm.complete()` → сохранить assistant Message → вернуть response
4. DialogueAgent → добавить в буфер
5. Через 5 секунд: DialogueAgent → `event_bus.publish(BusMessage topic=INPUT)`
6. EventBus → подписчики: Tracker (создать TraceEvent), EchoAgent (callback)
7. EchoAgent → обработать → `event_bus.publish(BusMessage topic=OUTPUT)`
8. EventBus → подписчики: Tracker (TraceEvent), OutputRouter (callback)
9. OutputRouter → `dialogue_agent.deliver_output(user_id, content)`
10. VS UI → polling → `GET /api/trace-events` → отобразить в Timeline

**Reset между тестами:**
1. Остановить активные процессы (прервать фоновые задачи)
2. `storage.clear()` → DELETE FROM всех таблиц
3. `dialogue_agent.reset()` → очистить буферы в памяти
4. `processing_layer.reset()` → пересоздать агентов

### 3.5. Изменения в существующем коде

Нет существующего кода. Создаётся новая codebase с нуля.

## 4. План реализации

**Рекомендуемый порядок (снизу-вверх):**

1. **Models (1 день)**
   - Создать структуру директорий
   - Реализовать все dataclasses в `models/`
   - Unit-тесты: проверка создания объектов, валидность типов

2. **Storage (2 дня)**
   - Создать `schema.sql`
   - Реализовать `IStorage` с aiosqlite
   - Unit-тесты: CRUD операции для каждой сущности

3. **EventBus (1 день)**
   - Реализовать `IEventBus` с in-memory pub/sub
   - Unit-тесты: подписка, публикация, множественные подписчики

4. **Tracker (1 день)**
   - Реализовать `ITracker` с подпиской на EventBus
   - Unit-тесты: track(), подписка, создание TraceEvents

5. **LLMProvider (1 день)**
   - Реализовать `ILLMProvider` с Anthropic API
   - Unit-тесты: mock API ответ, проверка формата запроса/ответа

6. **DialogueBuffer + DialogueAgent (3 дня)**
   - Реализовать DialogueBuffer
   - Реализовать `IDialogueAgent` с фоновым таймером
   - Unit-тесты: handle_message, буферизация, публикация

7. **ProcessingAgent (Echo) + ProcessingLayer (2 дня)**
   - Реализовать EchoAgent
   - Реализовать ProcessingLayer
   - Unit-тесты: подписка, обработка input, публикация output

8. **OutputRouter (1 день)**
   - Реализовать `IOutputRouter` (passthrough)
   - Unit-тесты: подписка, доставка в DialogueAgent

9. **Application (Bootstrap) (1 день)**
   - Реализовать `IApplication` с последовательной инициализацией
   - Интеграционные тесты: полный цикл bootstrap/shutdown

10. **HTTP API (FastAPI) (2 дня)**
    - Реализовать все эндпоинты
    - Unit-тесты: запросы к API (TestClient)

11. **SIM (1 день)**
    - Реализовать `ISim` с hardcoded сценарием
    - Тесты: запуск сценария, проверка отправки сообщений

12. **VS UI (2 дня)**
    - Создать React+Vite приложение
    - Реализовать polling client
    - Реализовать Timeline view
    - Ручное тестирование: запуск, проверка отображения

13. **Интеграционный тест (1 день)**
    - End-to-end тест: SIM → Core → VS UI
    - Проверка всех AC из task_brief

**Всего:** ~20 дней работы (с учетом отладки и доработок)

## 5. Технические критерии приемки

- [ ] TC-1: Все модели реализованы как dataclasses с корректными типами
- [ ] TC-2: Storage создаёт таблицы при init, сохраняет/читает все сущности
- [ ] TC-3: EventBus доставляет BusMessages всем подписчикам, персистит в Storage
- [ ] TC-4: Tracker создаёт TraceEvents через оба канала (подписка + track())
- [ ] TC-5: LLMProvider возвращает ответы от Claude API (или mock для тестов)
- [ ] TC-6: DialogueAgent обрабатывает handle_message, буферизует, публикует по таймауту
- [ ] TC-7: EchoAgent подписан на INPUT, публикует в OUTPUT
- [ ] TC-8: OutputRouter пересылает output в DialogueAgent
- [ ] TC-9: HTTP API отвечает на все эндпоинты (статус 200, валидный JSON)
- [ ] TC-10: SIM отправляет hardcoded сообщения, логирует ответы
- [ ] TC-11: VS UI отображает TraceEvents в Timeline (новые сверху)
- [ ] TC-12: Application.start() запускает все компоненты в правильном порядке
- [ ] TC-13: Application.reset() очищает данные, перезапускает систему
- [ ] TC-14: Unit-тесты покрывают все компоненты (минимум 70% coverage)
- [ ] TC-15: Интеграционный тест: SIM → API → DialogueAgent → EventBus → EchoAgent → OutputRouter → Timeline
- [ ] TC-16: Все TraceEvents из AC-8 записываются и видны в VS UI

## 6. Важные детали для Developer

### Asyncio и фоновые задачи
- **DialogueAgent буферизация:** Использовать `asyncio.create_task()` для фонового таймера. Не забыть сохранить task и отменить при `stop()`.
- **EventBus publish:** Использовать `asyncio.gather(*callbacks, return_exceptions=True)` для параллельного вызова подписчиков.
- **Storage connections:** aiosqlite требует одно соединение на корутину. Создавать connection при `init()` и закрывать при `close()`.

### UUID генерация
- Использовать стандартную библиотеку `uuid.uuid4()` для генерации ID.
- В Storage: если ID не передан, генерировать автоматически.

### Таймзоны
- Всегда использовать `datetime.now(timezone.utc)` для timestamp.
- При чтении из SQLite (который не хранит timezone): `timestamp.replace(tzinfo=timezone.utc)`.

### LLM API ошибки
- Anthropic API может возвращать ошибки (rate limit, invalid request). Пробрасывать исключение наверх.
- В DialogueAgent: ловить ошибки LLM, логировать, возвращать "Извините, ошибка" как ответ.

### HTTP API детали
- **FastAPI CORS:** Включить CORS для VS UI (разные порты: 8000 и 5173).
- **Query параметры:** Использовать `datetime.fromisoformat()` для парсинга `after` параметра.

### SQLite ограничения
- aiosqlite не поддерживает multiple statements в одном `execute()`. Использовать `executescript()` для `schema.sql`.
- В `get_messages()` и `get_trace_events()`: использовать parameterized queries (`?` placeholders) для защиты от SQL injection.

### VS UI polling
- Использовать `useEffect` с cleanup для clearInterval при размонтировании компонента.
- Избегать race conditions: если предыдущий запрос еще идет, не отправлять новый.

### Testing детали
- **Unit-тесты:** Использовать `pytest` + `pytest-asyncio` для async тестов.
- **Mock LLM:** Создать mock для LLMProvider, возвращающий фиктивные ответы (без реальных API calls).
- **Интеграционный тест:** Запускать Application в отдельном процессе (или использовать pytest fixtures с setUp/tearDown).

### Конфигурация
- **Environment variables:** Использовать `python-dotenv` для загрузки `.env` файла.
  - `ANTHROPIC_API_KEY`: ключ для Claude API
  - `DATABASE_URL`: путь к SQLite (по умолчанию `03_data/team_assistant.db`)
  - `API_HOST`: хост для HTTP API (по умолчанию `localhost`)
  - `API_PORT`: порт для HTTP API (по умолчанию `8000`)

### Логирование
- Использовать стандартный `logging` модуль с JSON formatter.
- Уровень: INFO для production, DEBUG для разработки.
- Каждый компонент логирует:start/stop, ключевые операции, ошибки.

### Путь к данным
- SQLite БД: `03_data/team_assistant.db` (создаётся автоматически).
- Логи: `04_logs/app.log` (rotating file handler).

### TypeScript типы
- Создать `src/types.ts` с интерфейсами для TraceEvent, Message (по аналогии с Python models).
- Использовать `interface` не `type` для совместимости с React props.
