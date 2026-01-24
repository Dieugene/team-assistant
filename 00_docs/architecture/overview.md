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
│  │              (in-memory pub/sub + persistence)             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↑                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Dialogue & Notify Agents                      │ │
│  │         (единая диалоговая система)                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↓                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Processing Agents                             │ │
│  │         (подключаемые модули через интерфейс)              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     Storage                               │ │
│  │  (инфраструктурный слой: messages, events, state)         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
           ↑                              ↑
    ┌──────────────┐              ┌──────────────┐
    │     SIM      │              │    VS UI     │
    │  (Generator) │              │   (polling)  │
    └──────────────┘              └──────────────┘
```

### 2.2 Уровни абстракции

**Прикладной уровень:**
- Dialogue & Notify Agents — диалоговая система
- Processing Agents — подключаемые модули обработки
- SIM — генератор тестовых данных
- VS UI — визуализация

**Транспортный уровень:**
- Event Bus — шина событий для коммуникации

**Инфраструктурный уровень:**
- Storage — персистентное хранение всех данных

---

## 3. Детальное описание модулей

### 3.1 Dialogue & Notify Agents (единая диалоговая система)

**Назначение:** AI-ассистент для каждого пользователя, который ведет диалог и доставляет уведомления.

**Ключевая логика:**

```python
class DialogueAgent:
    """
    AI-ассистент для ведения диалога с пользователем.
    """
    async def on_message(self, user_id: str, message: str):
        # 1. Генерация ответа через LLM
        response = await self.llm.generate_response(
            user_context=await self.get_user_context(user_id),
            message=message
        )

        # 2. Отправка ответа пользователю
        await self.send_to_user(user_id, response)

        # 3. Сохранение в историю
        await self.storage.save_message(user_id, message, response)

        # 4. Проверка завершения диалога (для упаковки в шину)
        if self.check_dialogue_complete(user_id):
            await self.package_dialogue(user_id)
```

**Диалоговая политика (единая для Dialogue и Notify):**
- Стиль коммуникации (формальный/неформальный)
- Уровень детализации ответов
- Правила поведения (когда переспрашивать, когда уточнять)
- Контекст пользователя (роль, текущий фокус, интересы)

**Детекция завершения диалога:**
- Явный маркер ("всё, спасибо")
- Таймаут (пауза > N минут)
- Внутри DialogueAgent как метод

**Notify Agent:**
- Инициирует диалог для доставки уведомлений
- Использует ту же диалоговую политику, что и Dialogue Agent
- Получает уведомления от Processing Agents (они сами помечают что кому доставить)
- Проверяет дубликаты через историю доставки

**Формирует события:**
```python
# При завершении диалога
{
    "type": "dialogue_boundary",
    "user_id": "user-1",
    "reason": "timeout",
    "messages": [...]
}

# При доставке уведомления
{
    "type": "notification_sent",
    "from_user": "user-1",
    "to_user": "user-2",
    "content": "...",
    "source_agent": "TaskManager"
}
```

---

### 3.2 Processing Agents (подключаемые модули)

**Назначение:** Обработка данных из Event Bus, управление сущностями, принятие решений о доставке.

**Архитектурные принципы:**
- **Подключаемые через интерфейс** — единый контракт для всех агентов
- Каждый агент имеет свой state и memory
- Все используют LLM (SGR Agent Core или другие подходы)
- **Агенты сами решают** кому что доставить (помечают recipients)

**Базовый интерфейс:**

```python
class IProcessingAgent(ABC):
    """Интерфейс для подключения обработчиков"""

    id: str
    name: str

    async def start(self): ...
    async def stop(self): ...

    async def process(
        self,
        message: BusMessage,
        context: ProcessingContext
    ) -> ProcessingResult: ...

    async def get_state(self) -> AgentState: ...
    async def save_state(self, state: AgentState): ...


class ProcessingResult(TypedDict):
    """Результат обработки"""
    entities: list[Entity]           # Извлеченные/обновленные сущности
    notifications: list[Notification]  # Кому что доставить
    reasoning: Optional[str]         # Reasoning trace для VS UI
```

**Примеры агентов:**

**TaskManager:**
- Отслеживает задачи и сроки
- Ведет базу задач (создание, обновление, закрытие)
- Соотносит задачи из сообщений с существующими в базе
- Помечает ответственных и дедлайны
- Отправляет уведомления о приближении сроков

**ContextManager:**
- Отслеживает движение информации между пользователями
- Определяет что из входящих данных может быть полезно конкретному пользователю
- Помечает: "это нужно User-X в его задачах"
- Анализирует контекст каждого пользователя (текущий фокус, роль)

**Future agents:**
- RiskDetector — выявление рисков и конфликтов
- DependencyFinder — поиск связей между задачами
- DeadlineWatcher — мониторинг сроков
- (любые другие через единый интерфейс)

**Развитие системы агентов:**
- Сначала: рамочная система с интерфейсом `IProcessingAgent`
- Когда рамочная система готова: отдельная ветка разработки агентов
- Tech Lead НЕ занимается составом агентов

---

### 3.3 Event Bus (транспортный уровень)

**Назначение:** Шина событий для коммуникации между модулями.

**Реализация:**
- In-memory pub/sub (EventEmitter pattern)
- Персистентность в Storage (все события сохраняются)
- Топики: `raw`, `processed`

**Интерфейс:**

```python
class IEventBus(ABC):
    """Шина событий"""

    async def publish(self, topic: Topic, message: BusMessage) -> MessageId:
        """Публикация события"""

    async def subscribe(self, topic: Topic, handler: Handler) -> Subscription:
        """Подписка на события"""

    async def get_history(self, topic: Topic, filter: Filter) -> list[BusMessage]:
        """Чтение истории событий"""
```

**Соотношение с Storage:**
- Event Bus — транспортный уровень (коммуникация)
- Storage — инфраструктурный уровень (персистентность)
- Event Bus использует Storage для сохранения событий

---

### 3.4 Storage (инфраструктурный уровень)

**Назначение:** Персистентное хранение всех данных системы.

**Сущности:**

| Сущность | Описание |
|----------|----------|
| `messages` | Сообщения пользователей (диалоги) |
| `events` | События из Event Bus (для VS UI и replay) |
| `agent_conversations` | Истории диалогов processing agents (SGR) |
| `agent_states` | Состояния processing agents |
| `tasks` | Задачи (TaskManager) |
| `user_contexts` | Контексты пользователей (роль, фокус, интересы) |
| `notifications_log` | Лог доставленных уведомлений |

**Интерфейс:**

```python
class IStorage(ABC):
    """Единый интерфейс хранения"""

    # Messages
    async def save_message(self, msg: Message): ...
    async def get_messages(self, filter: Filter): ...

    # Events
    async def save_event(self, event: BusMessage): ...
    async def get_events(self, filter: Filter): ...

    # Agent conversations
    async def save_conversation(self, agent_id: str, conv: list): ...
    async def load_conversation(self, agent_id: str): ...

    # Agent states
    async def save_agent_state(self, agent_id: str, state: dict): ...
    async def load_agent_state(self, agent_id: str): ...

    # Tasks (TaskManager)
    async def save_task(self, task: Task): ...
    async def get_tasks(self, filter: Filter): ...

    # User contexts
    async def save_user_context(self, user_id: str, ctx: UserContext): ...
    async def get_user_context(self, user_id: str): ...
```

**Dev/Prod:**
- Dev: SQLite (файл, ноль деплоя, JSON поддержка)
- Prod: YDB или другое решение (соотв. рос. законодательству)

**ADR:** Будет отдельное решение по выбору БД для продакшена.

**Абстракции над Storage:**
- Модули могут иметь промежуточный слой (Repository pattern)
- Пример: `TaskRepository` над Storage для работы с задачами
- Пример: `UserContextRepository` для работы с контекстами

---

### 3.5 SIM (Simulation Layer)

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
- Генерирует события в Event Bus

---

### 3.6 VS UI (Visualization Service)

**Назначение:** Наглядная визуализация для наблюдаемости.

**Общие рамки:**
- Polling API для получения данных
- Timeline + swimlanes как основные виды
- Agent reasoning traces для отладки

**Детальная архитектура:** См. `00_docs/architecture/visualization.md`

---

## 4. Event Tracking Strategy

### 4.1 Гибридный подход

**Прямой трекинг** (для того, что не в основном storage):
```python
await events.track('agent_reasoning_step', {...})
await events.track('dialogue_boundary', {...})
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
| **Event Bus** | In-memory + persistence | EventEmitter + Storage |

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

**Детали:** См. `00_docs/architecture/visualization.md`

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
class TaskManagerAgent(SGRToolCallingAgent):
    """
    Reasoning: анализ задачи через LLM
    Action: сохранение/обновление в базе через tool
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
    "reasoning": "Анализирую задачу...",
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
User → DialogueAgent → Storage (messages)
      → [dialogue complete] → EventBus (raw)
      → ProcessingAgent → EventBus (processed) → Storage
```

### 8.2 От системы к пользователю

```
EventBus (processed) → ProcessingAgent
      → [agent решает: уведомить User-B] → EventBus (processed)
      → NotifyAgent → User-B
```

### 8.3 Между пользователями

```
User-A сообщает → EventBus → ProcessingAgent (TaskManager)
      → [TaskManager: нужно уведомить User-B] → EventBus
      → NotifyAgent-B → User-B получает
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
class IProcessingAgent(ABC): ...
class ILLMProvider(ABC): ...

# Dev-реализации
SQLiteStorage()
InMemoryEventBus()

# Prod-реализации (будет)
YDBStorage()
```

### 9.4 Интерфейсы для расширения

**Processing Agents:**
- Единый интерфейс `IProcessingAgent`
- Подключение через регистрацию в системе
- State management через Storage
- Когда рамочная система готова — отдельная ветка разработки агентов

---

## 10. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| Детальная архитектура VS UI | См. `visualization.md` |
| Выбор БД для продакшена | ADR позже |
| Фронтенд-стек для VS | См. `visualization.md` |
| DI-контейнер детализация | Tech Lead |
| Конкретные Processing Agents | Отдельная ветка разработки после рамочной системы |

---

## 11. Следующие шаги

1. ✅ Архитектура зафиксирована (этот документ)
2. ✅ Визуализация — отдельный документ (`visualization.md`)
3. → **Tech Lead:** Создать `implementation_plan.md`, `backlog.md`, task briefs
4. → **ADR:** Выбор БД для продакшена (когда станет актуально)

---

**Документ:** `00_docs/architecture/overview.md`
**Архитектор:** Architect Agent (Sonnet 4.5)
**Дата:** 2025-01-24
