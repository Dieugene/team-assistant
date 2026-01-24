# Архитектура Team Assistant

**Дата:** 2025-01-24
**Статус:** Черновик для обсуждения

---

## 1. Введение

### 1.1 Цель проекта

Сервис коллективной работы на базе AI, где инструмент формируется вокруг естественных коммуникаций, а не человек подстраивается под инструмент.

**Ключевая идея:**
- Каждый участник взаимодействует со своим AI-ассистентом
- Ассистенты обмениваются информацией через общую шину
- Структуры (задачи, сроки, связи) формируются автоматически

### 1.2 Проблема

Существующие инструменты (Trello, task trackers) требуют адаптации к заданным онтологиям. Люди устают от необходимости "жить" в системе и откатываются к примитивным средствам (Google Docs, чаты).

### 1.3 Решение

Инверсия модели: минимальный порог входа через естественный диалог, онтология формируется под команду.

### 1.4 Стратегия разработки

**Сначала:** ядро системы + визуализация для отладки
**Потом:** фронтенд для пользователей (Telegram-бот, приложение)

**Приоритеты на старте:**
- ✅ Проверка гипотезы (< 50 пользователей)
- ✅ **Наблюдаемость** — люди должны видеть что происходит
- ✅ Симуляция для тестирования без реальных пользователей
- ✅ Скорость разработки

---

## 2. Общая архитектура

### 2.1 Схема системы

```
┌─────────────────────────────────────────────────────────────────┐
│                     Core Process (один процесс)                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Event Bus                              │ │
│  │              (in-memory pub/sub + storage)                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↑                                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐ │
│  │  Dialogue  │  │   Notify   │  │   Processing Agents      │ │
│  │   Agent    │  │   Agent    │   │   (подключаемые модули) │ │
│  └────────────┘  └────────────┘  └──────────────────────────┘ │
│        ↓               ↓                      ↓                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     Storage                               │ │
│  │  • messages  • events  • agent_conversations             │ │
│  │  • agent_states  • reasoning_traces                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
           ↑                              ↑
    ┌──────────────┐              ┌──────────────┐
    │     SIM      │              │    VS UI     │
    │  (Generator) │              │   (polling)  │
    └──────────────┘              └──────────────┘
```

### 2.2 Ключевые модули

| Модуль | Назначение | Заметки |
|--------|------------|---------|
| **Dialogue Agent** | Ведение диалога с пользователем | Проверка завершения диалога внутри |
| **Notify Agent** | Доставка уведомлений пользователям | Фильтрация через историю доставки |
| **Processing Agents** | Обработка данных в шине | Подключаемые модули, используют LLM |
| **Event Bus** | Шина данных для коммуникации | In-memory pub/sub + персистентность |
| **Storage** | Хранение всех данных | SQLite (dev) / YDB (prod) |
| **SIM** | Эмуляция пользователей для тестов | Генератор сообщений |
| **VS UI** | Визуализация для наблюдаемости | Polling API, timeline + swimlanes |

---

## 3. Детальное описание модулей

### 3.1 Dialogue Agent

**Назначение:** Ведение диалога с пользователем, сохранение в буфер, детекция завершения.

**Ключевая логика:**
```python
class DialogueAgent:
    async def on_message(self, user_id: str, message: str):
        # 1. Добавляем в буфер
        await self.storage.append_to_buffer(user_id, message)

        # 2. Проверяем завершение диалога
        if self.check_dialogue_complete(user_id):
            # 3. Упаковываем и отправляем в шину
            await self.package_dialogue(user_id)
```

**Детекция завершения диалога (бывший DBD):**
- Явный маркер ("всё, спасибо")
- Таймаут (пауза > N минут)
- Внутри DialogueAgent как метод

**Формирует событие:**
```python
{
    "type": "dialogue_boundary",
    "user_id": "user-1",
    "reason": "timeout",
    "messages": [...]
}
```

---

### 3.2 Notify Agent

**Назначение:** Доставка уведомлений от Processing Agents пользователям.

**Ключевая логика:**
```python
class NotifyAgent:
    async def on_processed_event(self, event: ProcessedEvent):
        # 1. Проверяем релевантность для пользователя
        if await self.is_relevant(event.to_user, event):
            # 2. Проверяем дубликаты (семантические)
            if not await self.already_delivered(event.to_user, event):
                # 3. Доставляем
                await self.deliver(event.to_user, event)
```

**Фильтрация:**
- История доставки (хранится в storage)
- Семантическая дедупликация (через LLM)

---

### 3.3 Processing Agents

**Назначение:** Обработка данных из Event Bus, извлечение сущностей.

**Архитектурные принципы:**
- Подключаемые модули
- Каждый агент имеет свой state и memory
- Все используют LLM
- Могут использовать разные подходы (SGR, function calling, другие)

**Базовый интерфейс:**
```python
class BaseProcessingAgent(ABC):
    id: str
    name: str

    async def start(self): ...

    async def process(
        self,
        message: BusMessage,
        context: ProcessingContext
    ) -> ProcessingResult: ...

    async def get_state(self) -> AgentState: ...
```

**Примеры агентов (определяются позже):**
- TaskExtractor — извлечение задач
- DeadlineTracker — отслеживание сроков
- DependencyFinder — поиск связей

---

### 3.4 Event Bus

**Назначение:** Шина данных для коммуникации между модулями.

**Реализация:**
- In-memory pub/sub (EventEmitter pattern)
- Персистентность в Storage
- Топики: `raw`, `processed`, `outbound`

**Интерфейс:**
```python
class IEventBus(ABC):
    async def publish(self, topic: Topic, message: BusMessage): ...
    async def subscribe(self, topic: Topic, handler: Handler): ...
    async def get_history(self, topic: Topic, filter: Filter): ...
```

---

### 3.5 Storage

**Назначение:** Персистентное хранение всех данных.

**Таблицы/коллекции:**
- `messages` — сообщения пользователей
- `events` — события для VS UI
- `agent_conversations` — истории диалогов агентов
- `agent_states` — состояния агентов
- `reasoning_traces` — reasoning шаги (для SGR)

**Интерфейс:**
```python
class IStorage(ABC):
    # Messages
    async def save_message(self, msg: Message): ...
    async def get_messages(self, filter: Filter): ...

    # Events (для VS)
    async def save_event(self, event: TimelineEvent): ...
    async def get_events(self, filter: Filter): ...

    # Agent conversations
    async def save_conversation(self, agent_id: str, conv: list): ...
    async def load_conversation(self, agent_id: str): ...

    # Agent states
    async def save_agent_state(self, agent_id: str, state: dict): ...
    async def load_agent_state(self, agent_id: str): ...
```

**Dev/Prod:**
- Dev: SQLite (файл, ноль деплоя)
- Prod: YDB или другое решение (соотв. рос. законодательству)

**ADR:** Будет отдельное решение по выбору БД для продакшена.

---

### 3.6 SIM (Simulation Layer)

**Назначение:** Эмуляция пользователей для тестирования.

**Компоненты:**
- `SIM.profiles` — профили виртуальных пользователей (роль, характер, зона ответственности)
- `SIM.scenario` — события внешнего мира как триггеры
- `SIM.engine` — генератор: профиль + событие → сообщение

**Качество сообщений:**
- ≥ 2-3 конкретных факта (имена, сроки, суммы)
- Эмоциональная окраска или проблема
- ❌ "Обсудили задачу, всё хорошо"
- ✅ "Иван из закупок сообщил об отставании поставки X на 2 недели"

**Интеграция:**
- Подключается к DialogueAgent как обычный пользователь
- Генерирует события в VS UI для отладки

---

### 3.7 VS UI (Visualization Service)

**Назначение:** Наглядная визуализация для наблюдаемости.

**Общие рамки (детали — отдельный архитектор):**

**Backend API:**
```python
# Polling endpoint
GET /api/timeline?since=2025-01-24T10:00:00

Response:
{
    "events": [
        {"timestamp": "...", "type": "message_received", "user_id": "...", ...},
        {"timestamp": "...", "type": "dialogue_boundary", ...},
        {"timestamp": "...", "type": "agent_reasoning", ...}
    ]
}
```

**Frontend views:**
- **Timeline** — графический timeline (НЕ текстовый список)
- **Swimlanes** — дорожки по пользователям / объектам
- **User Context** — детализация по клику
- **Agent Reasoning** — что думают агенты (SGR traces)

**Коммуникация:**
- Polling (простота)
- Задержка 1+ секунда — норма

**Фронтенд-стек:** Выбирается по критериям наглядности + простоты разработки.

---

## 4. Event Tracking Strategy

### 4.1 Гибридный подход

**Прямой трекинг** (для того, что не в основном storage):
```python
await events.track('dialogue_boundary', {...})
await events.track('agent_reasoning_step', {...})
```

**Извлечение из storage** (для основных данных):
```python
class VSDataSource:
    async def get_timeline(self, filter):
        tracked = await self.tracking_storage.get_events(filter)
        extracted = await self.extractor.extract_from_main_storage(filter)
        return self.merge(tracked, extracted)
```

### 4.2 Event Tracker

Аналог Amplitude SDK:
```python
class EventTracker:
    async def track(self, event_name: str, data: dict):
        """Фиксирует событие для визуализации"""
        event = TimelineEvent(
            timestamp=datetime.now(),
            type=event_name,
            data=data
        )
        await self.storage.save_event(event)
```

---

## 5. Технологический стек

### 5.1 Backend

| Компонент | Технология | Обоснование |
|-----------|------------|-------------|
| **Язык** | Python | Лучшая экосистема для LLM |
| **Framework** | FastAPI | Async, type hints, auto OpenAPI |
| **LLM Integration** | SGR Agent Core | Schema-Guided Reasoning фреймворк |
| **Storage Dev** | SQLite | Файл, ноль деплоя, JSON поддержка |
| **Storage Prod** | YDB (TBD) | ADR позже |
| **Event Bus** | In-memory + Storage | Простой EventEmitter |

### 5.2 LLM Provider Layer

Слой с ретраями для rate limits:
```python
class LLMProviderWithRetry:
    async def complete(self, prompt: str) -> str:
        return await self._retry_with_backoff(
            lambda: self.base_provider.complete(prompt)
        )

    async def _retry_with_backoff(self, func):
        # Exponential backoff: 2, 4, 8, 16, 32 сек
        ...
```

**Провайдеры:**
- OpenAI
- Anthropic

### 5.3 Frontend (VS UI)

**Требования:**
- Наглядность
- Простота разработки
- Timeline + swimlanes

**Библиотеки для изучения:**
- Vis.js Timeline
- D3.js
- React Flow

**Детали:** Отдельный архитектор для VS.

---

## 6. SGR Agent Core Integration

### 6.1 Что такое SGR

**SGR = Schema-Guided Reasoning**

Фреймворк для создания AI-агентов с явным reasoning через structured JSON schemas.

**Цикл агента:**
1. **Reasoning Phase** — LLM структурированно отвечает какой tool вызывать
2. **Select Action Phase** — выбор tool
3. **Action Phase** — выполнение tool

**Типы агентов:**
- `SGRAgent` — полностью на Structured Output
- `ToolCallingAgent` — нативный function calling
- `SGRToolCallingAgent` — гибрид

### 6.2 Использование в проекте

**Processing Agents на базе SGR:**
```python
class TaskExtractorAgent(SGRToolCallingAgent):
    """
    Reasoning: анализ сообщения через LLM
    Action: сохранение задачи через tool
    """
```

**Conversation storage:**
```python
# SGR хранит conversation в памяти: agent.conversation
# Наш storage сохраняет для персистентности
await storage.save_conversation(agent.id, agent.conversation)
```

**Reasoning traces для VS UI:**
```python
# Reasoning phase возвращает структуру
{
    "reasoning": "Анализирую сообщение...",
    "selected_tool": "save_task",
    "tool_arguments": {...}
}

# Сохраняем для визуализации
await events.track('agent_reasoning', {
    'agent_id': agent.id,
    'reasoning': reasoning
})
```

---

## 7. Ограничения и требования

### 7.1 Технические

- **Масштаб:** < 50 пользователей на MVP
- **Deployment:** Локальная разработка без сложной инфры
- **Data persistence:** SQLite для dev, продакшен — TBD

### 7.2 Бизнес

- **Наблюдаемость** — критично для демонстрации
- **Симуляция** — обязательно для тестов без реальных пользователей
- **LLM costs** — кэширование там где возможно

### 7.3 Regulatory

- **Продакшен БД:** Должна соответствовать рос. законодательству (YDB и др.)
- **Data residency:** Учет требований к хранению данных

---

## 8. Потоки данных

### 8.1 От пользователя в систему

```
User → DialogueAgent → Storage (buffer)
      → [dialogue complete] → EventBus (raw)
      → ProcessingAgent → EventBus (processed)
```

### 8.2 От системы к пользователю

```
EventBus (processed) → NotifyAgent
      → [check relevance] → EventBus (outbound)
      → DialogueAgent → User
```

### 8.3 Между пользователями

```
User-A сообщает → EventBus → Processing
      → EventBus → Notify-Agent-B → User-B получает
```

---

## 9. Принципы разработки

### 9.1 MVP-first

- Простейшая работающая система
- Избегать over-engineering
- Сложность — только когда необходимость доказана

### 9.2 Observability-first

- Каждое действие → событие в timeline
- VS UI показывает "что происходит"
- Reasoning агентов должен быть видим

### 9.3 Порты и адаптеры

```python
# Интерфейсы
class IStorage(ABC): ...
class IEventBus(ABC): ...
class ILLMProvider(ABC): ...

# Dev-реализации
InMemoryStorage()
SQLiteStorage()

# Prod-реализации (будет)
YDBStorage()
KafkaEventBus()
```

---

## 10. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| Конкретный состав Processing Agents | Отложено до Tech Lead |
| Детальная архитектура VS UI | Отложено до отдельного архитектора |
| Выбор БД для продакшена | ADR позже |
| Фронтенд-стек для VS | Отложено до архитектора VS |
| DI-контейнер детализация | Tech Lead |

---

## 11. Следующие шаги

1. ✅ Архитектура зафиксирована (этот документ)
2. → **Tech Lead:** Создать `implementation_plan.md`, `backlog.md`, task briefs
3. → **Architect VS:** Детальная архитектура визуализации (отдельная сессия)
4. → **ADR:** Выбор БД для продакшена (когда станет актуально)

---

**Документ:** `00_docs/architecture/overview.md`
**Архитектор:** Architect Agent (Sonnet 4.5)
**Дата:** 2025-01-24
