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

#### 3.1.1 DialogueAgent

**Точки активации:**
1. **По сообщению пользователя** — `on_message(user_id, message)`
2. **По таймауту** — фоновый процесс проверяет неактивные диалоги
3. **По событию из Event Bus** — реакция на события для proactive коммуникации

**Архитектура:**

```python
class DialogueAgent:
    """
    AI-ассистент для ведения диалога с пользователем.
    Управляет множеством диалогов одновременно.
    """

    def __init__(self):
        self.active_dialogues: dict[str, DialogueState] = {}  # user_id -> состояние
        self.dialogue_policy: DialoguePolicy = ...  # Единая политика (см. ниже)
        self.timeout_checker = BackgroundTask(...)  # Фоновая проверка таймаутов

    async def start(self):
        """Запуск агента: загрузка активных диалогов"""
        self.active_dialogues = await self.load_active_dialogues()
        self.timeout_checker.start(self.check_timeouts, interval=60s)

    async def on_message(self, user_id: str, message: str):
        """Обработка входящего сообщения"""
        # 1. Загрузка/обновление состояния диалога
        dialogue = self.get_or_create_dialogue(user_id)
        dialogue.last_activity = datetime.now()

        # 2. Трекинг для VS UI
        await self.events.track('message_received', {
            'user_id': user_id,
            'content': message
        })

        # 3. Генерация ответа через LLM
        user_context = await self.load_user_context(user_id)
        response = await self.llm.generate_response(
            dialogue_policy=self.dialogue_policy,
            user_context=user_context,
            message=message,
            dialogue_history=dialogue.history
        )

        # 4. Отправка ответа пользователю
        await self.send_to_user(user_id, response)

        # 5. Трекинг ответа для VS UI
        await self.events.track('message_sent', {
            'user_id': user_id,
            'content': response
        })

        # 6. Сохранение в историю
        dialogue.history.append((message, response))
        await self.storage.save_message(user_id, message, response)

        # 7. Проверка завершения диалога
        if self.check_dialogue_complete(dialogue):
            await self.package_dialogue(user_id, dialogue)

    async def check_timeouts(self):
        """Фоновая проверка таймаутов (вызывается periodic task)"""
        now = datetime.now()
        for user_id, dialogue in self.active_dialogues.items():
            if now - dialogue.last_activity > DIALOGUE_TIMEOUT:
                await self.package_dialogue(user_id, dialogue, reason='timeout')

    async def on_bus_event(self, event: BusMessage):
        """Реакция на события из Event Bus для proactive коммуникации"""
        # Пример: ProcessingAgent обнаружил критический срок
        # → NotifyAgent инициирует диалог с пользователем
        if event.type == 'deadline_alert':
            user_id = event.user_id
            await self.initiate_dialogue(user_id, event.data)

    def check_dialogue_complete(self, dialogue: DialogueState) -> bool:
        """Проверка условий завершения диалога"""
        # Явный маркер в последнем сообщении
        if dialogue.has_explicit_closing_marker():
            return True
        # Достигнут лимит сообщений
        if dialogue.message_count > MAX_MESSAGES:
            return True
        return False

    async def package_dialogue(self, user_id: str, dialogue: DialogueState, reason: str = 'complete'):
        """Упаковка завершенного диалога в Event Bus"""
        event = {
            "type": "dialogue_boundary",
            "user_id": user_id,
            "reason": reason,
            "messages": dialogue.history,
            "timestamp": datetime.now()
        }
        await self.event_bus.publish('raw', event)
        del self.active_dialogues[user_id]  # Удаляем из активных
```

**Состояние диалога (DialogueState):**
```python
class DialogueState:
    user_id: str
    history: list[tuple[str, str]]  # [(user_msg, assistant_response), ...]
    last_activity: datetime
    started_at: datetime
    metadata: dict  # Доп. данные диалога
```

**Диалоговая политика (DialoguePolicy):**
```python
class DialoguePolicy:
    """Единая политика для Dialogue и Notify Agents"""
    communication_style: Literal['formal', 'informal', 'neutral']
    detail_level: Literal['concise', 'normal', 'detailed']
    behavior_rules: dict  # Когда переспрашивать, когда уточнять
    # Загружается из UserContext (см. Storage)
```

#### 3.1.2 NotifyAgent

**Назначение:** Доставка уведомлений от Processing Agents пользователям через диалог.

```python
class NotifyAgent:
    """
    Использует ту же диалоговую политику, что и DialogueAgent.
    Инициирует диалог proactive или доставляет в рамках существующего.
    """
    dialogue_policy: DialoguePolicy  # Общая с DialogueAgent
    delivery_queue: dict[str, list[Notification]]  # user_id -> накопленные уведомления

    async def on_processing_notification(self, notification: Notification):
        """Обработка уведомления от ProcessingAgent"""
        # 1. Проверка дубликатов через notifications_log в Storage
        if await self.is_duplicate(notification):
            return

        # 2. Трекинг генерации уведомления
        await self.events.track('notification_generated', {
            'from_agent': notification.source_agent,
            'to_user': notification.recipient_id,
            'content': notification.content
        })

        # 3. Добавление в очередь доставки
        self.delivery_queue[notification.recipient_id].append(notification)

        # 4. Если есть активный диалог с пользователем — доставляем сразу
        if notification.recipient_id in dialogue_agent.active_dialogues:
            await self.deliver_through_dialogue(notification)
        # Иначе — инициируем новый диалог или ждем следующего сообщения
        else:
            await self.initiate_delivery_dialogue(notification.recipient_id)

    async def deliver_through_dialogue(self, notification: Notification):
        """Доставка в рамках активного диалога"""
        user_id = notification.recipient_id

        # Формируем сообщение с учетом диалоговой политики
        user_context = await self.load_user_context(user_id)
        message = self.format_notification(notification, user_context, self.dialogue_policy)

        # Отправляем как если бы это был ответ ассистента
        await dialogue_agent.send_to_user(user_id, message)

        # Трекинг доставки
        await self.events.track('notification_sent', {
            'from_agent': notification.source_agent,
            'to_user': user_id,
            'content': notification.content
        })

        # Логируем доставку для проверки дубликатов
        await self.storage.save_notification_log(notification)
```

**Проверка дубликатов:**
```python
async def is_duplicate(self, notification: Notification) -> bool:
    """Проверка по notifications_log в Storage"""
    recent_logs = await self.storage.get_notifications_log(
        user_id=notification.recipient_id,
        since=datetime.now() - timedelta(hours=24)
    )
    # Дубликат если: тот же source_agent + похожий контент + было доставлено недавно
    return any(
        log.source_agent == notification.source_agent and
        self.similarity(log.content, notification.content) > 0.8
        for log in recent_logs
    )
```

---

### 3.2 Processing Agents (подключаемые модули)

**Назначение:** Обработка данных из Event Bus, управление сущностями, принятие решений о доставке.

**Архитектурные принципы:**
- **Подключаемые через интерфейс** — единый контракт для всех агентов
- Каждый агент имеет свой **state** и **memory** (см. Storage раздел)
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

    # State management (опционально, если агенту нужен персистентный state)
    async def get_state(self) -> AgentState: ...
    async def save_state(self, state: AgentState): ...


class ProcessingResult(TypedDict):
    """Результат обработки"""
    entities: list[Entity]           # Извлеченные/обновленные сущности
    notifications: list[Notification]  # Кому что доставить
    reasoning: Optional[ReasoningTrace]  # Reasoning trace для VS UI


class ReasoningTrace(TypedDict):
    """Структурированный reasoning SGR агента"""
    reasoning: str                   # Текстовое объяснение
    selected_tool: str               # Выбранный tool
    tool_arguments: dict             # Аргументы tool
    timestamp: datetime              # Время reasoning
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

**Назначение:** Универсальный персистентный слой для хранения всех данных системы.

**Принципы:**
- **Универсальность** — IStorage не зависит от бизнес-логики, работает с generic сущностями
- **Абстракция через репозитории** — бизнес-модули используют Repository pattern поверх Storage
- **State vs Memory** — см. ниже

**Интерфейс:**

```python
class IStorage(ABC):
    """Универсальный интерфейс хранения (низкоуровневый)"""

    # Generic CRUD operations
    async def save(self, entity_type: str, entity_id: str, data: dict): ...
    async def load(self, entity_type: str, entity_id: str) -> dict | None: ...
    async def delete(self, entity_type: str, entity_id: str): ...

    # Query operations
    async def query(self, entity_type: str, filter: Filter) -> list[dict]: ...
    async def exists(self, entity_type: str, filter: Filter) -> bool: ...

    # Transaction support
    async def begin_transaction(self) -> Transaction: ...
```

**Репозитории (бизнес-слой):**

Поверх IStorage строятся типизированные репозитории:

```python
class MessageRepository:
    """Работа с сообщениями диалогов"""
    def __init__(self, storage: IStorage):
        self.storage = storage

    async def save_message(self, msg: Message): ...
    async def get_messages(self, user_id: str, limit: int) -> list[Message]: ...

class TaskRepository:
    """Работа с задачами (TaskManager)"""
    def __init__(self, storage: IStorage):
        self.storage = storage

    async def save_task(self, task: Task): ...
    async def get_tasks(self, filter: TaskFilter) -> list[Task]: ...

class AgentStateRepository:
    """Работа с состояниями агентов"""
    def __init__(self, storage: IStorage):
        self.storage = storage

    async def save_state(self, agent_id: str, state: AgentState): ...
    async def load_state(self, agent_id: str) -> AgentState | None: ...

class AgentConversationRepository:
    """Работа с SGR conversation history"""
    def __init__(self, storage: IStorage):
        self.storage = storage

    async def save_conversation(self, agent_id: str, conv: list): ...
    async def load_conversation(self, agent_id: str) -> list: ...

class UserContextRepository:
    """Работа с контекстами пользователей"""
    def __init__(self, storage: IStorage):
        self.storage = storage

    async def save_context(self, user_id: str, ctx: UserContext): ...
    async def load_context(self, user_id: str) -> UserContext: ...

class NotificationLogRepository:
    """Работа с логом доставленных уведомлений"""
    def __init__(self, storage: IStorage):
        self.storage = storage

    async def save_log(self, notification: Notification): ...
    async def get_recent_logs(self, user_id: str, since: datetime) -> list[Notification]: ...
```

**State vs Memory:**

| Понятие | Описание | Где хранится | Когда сбрасывается |
|---------|----------|--------------|-------------------|
| **State** | Текущее состояние объекта на момент времени (какой-то агент имеет задачу X в статусе Y) | Storage (персистентно) | При обновлении состояния |
| **Memory** | История предыдущих состояний и действий (conversation history, message history) | Storage (персистентно) | Обычно никогда (архив) |
| **In-memory cache** | Кэш в RAM для быстрого доступа (агент держит state в памяти во время обработки) | RAM процесса | При перезапуске процесса / сервера |

**Пример для ProcessingAgent:**
- **State:** текущий счетчик, последний обработанный timestamp, флаги (хранится в Storage через `AgentStateRepository`)
- **Memory:** SGR conversation history — все reasoning + actions (хранится в Storage через `AgentConversationRepository`)
- **In-memory:** кэш загруженного state + conversation для текущей сессии (в RAM агента)

**Dev/Prod:**
- Dev: SQLite (файл, ноль деплоя, JSON поддержка)
- Prod: YDB или другое решение (соотв. рос. законодательству)

**ADR:** Будет отдельное решение по выбору БД для продакшена.

---

### 3.5 SIM (Simulation Layer)

**Назначение:** Эмуляция пользователей для тестирования без реальных людей.

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
SIM работает как замена пользователя — отправляет сообщения через `DialogueAgent.on_message()`:

```python
class SimEngine:
    async def generate_user_action(self, profile: SimProfile, scenario_event: ScenarioEvent):
        """Генерация действия виртуального пользователя"""
        message = self.compose_message(profile, scenario_event)

        # SIM отправляет сообщение как обычный пользователь
        await dialogue_agent.on_message(user_id=profile.user_id, message=message)
```

**Поток данных:**
```
SIM Engine → DialogueAgent.on_message() → ... → Event Bus (raw) → ProcessingAgents
```

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

### 4.1 Разница между Event Bus и Tracking

**Event Bus (транспортный уровень):**
- События для коммуникации между модулями
- Пример: `dialogue_boundary` → сигнал для ProcessingAgents начать обработку
- Сохраняются в Storage для replay и восстановления состояния

**Event Tracking (наблюдаемость):**
- События для визуализации в VS UI
- Пример: `message_received`, `agent_reasoning`, `notification_sent`
- Сохраняются в отдельном хранилище для timeline

**Пример с dialogue_boundary:**

```python
# 1. DialogueAgent публикует в Event Bus для ProcessingAgents
await event_bus.publish('raw', {
    "type": "dialogue_boundary",
    "user_id": "user-1",
    "reason": "timeout",
    "messages": [...]
})

# 2. Это же событие сохраняется в Storage для history (автоматически Event Bus)
# 3. Для VS UI трекаются отдельные события из диалога:
await events.track('message_received', {'user_id': 'user-1', 'content': '...'})
await events.track('message_sent', {'user_id': 'user-1', 'content': '...'})
# 4. Когда диалог завершен — трекается boundary для timeline
await events.track('dialogue_boundary_complete', {'user_id': 'user-1', 'reason': 'timeout'})
```

### 4.2 Гибридный подход VS DataSource

**Прямой трекинг** (для событий, которых нет в основном storage):
```python
await events.track('agent_reasoning', {...})      # Reasoning агента
await events.track('dialogue_boundary_complete', {...})  # Завершение диалога
await events.track('notification_generated', {...})     # Генерация уведомления
```

**Извлечение из storage** (для основных данных):
```python
class VSDataSource:
    async def get_timeline(self, filter):
        # Прямой трекинг
        tracked = await self.tracking_storage.get_events(filter)

        # Извлечение из основного storage
        extracted = []
        # Сообщения → конвертируем в timeline events
        messages = await self.message_repo.get_messages(filter)
        for msg in messages:
            extracted.append(self._message_to_timeline_event(msg))

        # События Event Bus → добавляем в timeline
        bus_events = await self.event_bus.get_history('raw', filter)
        for event in bus_events:
            extracted.append(self._bus_event_to_timeline_event(event))

        return self.merge(tracked, extracted)
```

### 4.3 Event Tracker

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

**Основные события для трекинга:**

| Событие | Когда трекается | Данные |
|---------|-----------------|--------|
| `message_received` | Пользователь отправил сообщение | user_id, content |
| `message_sent` | Ассистент отправил ответ | user_id, content |
| `dialogue_boundary_complete` | Диалог завершен | user_id, reason, message_count |
| `agent_reasoning` | Reasoning phase завершена | agent_id, reasoning (структура) |
| `agent_action` | Action phase выполнена | agent_id, tool, result |
| `notification_generated` | Агент решил уведомить | from_agent, to_user, content |
| `notification_sent` | Уведомление доставлено | from_agent, to_user, content |

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
    def __init__(self, storage: IStorage, event_tracker: EventTracker):
        self.conv_repo = AgentConversationRepository(storage)
        self.events = event_tracker

    async def process(self, message: BusMessage, context: ProcessingContext) -> ProcessingResult:
        # 1. SGR Reasoning Phase
        reasoning = await self._reasoning_phase(message)

        # 2. Трекинг reasoning для VS UI (сразу после получения)
        await self.events.track('agent_reasoning', {
            'agent_id': self.id,
            'timestamp': datetime.now(),
            'reasoning': reasoning
        })

        # 3. SGR Action Phase
        action_result = await self._execute_action(reasoning.selected_tool, reasoning.tool_arguments)

        # 4. Сохранение conversation в Storage (периодически или после action)
        await self.conv_repo.save_conversation(self.id, self.conversation)

        # 5. Формирование результата
        return ProcessingResult(
            entities=action_result.entities,
            notifications=action_result.notifications,
            reasoning=reasoning  # ReasoningTrace структура
        )
```

**State vs Memory в SGR агенте:**

```python
class TaskManagerAgent(SGRToolCallingAgent):
    # State (текущее состояние)
    state: AgentState  # → сохраняется через AgentStateRepository

    # Memory (история)
    conversation: list  # SGR internal conversation → сохраняется через AgentConversationRepository

    async def save_state(self, state: AgentState):
        """Вызывается системой периодически или при stop()"""
        await self.state_repo.save_state(self.id, state)
```

**Conversation storage:**
```python
# SGR хранит conversation в памяти: agent.conversation
# Наш storage сохраняет для персистентности через репозиторий
await conv_repo.save_conversation(agent.id, agent.conversation)
```

**Reasoning traces для VS UI:**

```python
# Reasoning phase возвращает структуру
{
    "reasoning": "Анализирую задачу...",
    "selected_tool": "save_task",
    "tool_arguments": {...}
}

# Сохраняем для визуализации внутри process() ДО выполнения action
await events.track('agent_reasoning', {
    'agent_id': agent.id,
    'timestamp': datetime.now(),
    'reasoning': reasoning
})
```

**Альтернатива: автоматически через SGR**

```python
# Можно настроить SGR на автоматический трекинг
class TaskManagerAgent(SGRToolCallingAgent):
    def __init__(self, ...):
        super().__init__(
            on_reasoning=self._track_reasoning,  # callback после reasoning
            on_action=self._track_action          # callback после action
        )

    async def _track_reasoning(self, reasoning: ReasoningTrace):
        await self.events.track('agent_reasoning', {
            'agent_id': self.id,
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
User → DialogueAgent.on_message()
    → Трекинг: message_received
    → LLM генерация ответа
    → Трекинг: message_sent
    → Storage: save_message (через MessageRepository)
    → [dialogue complete] → EventBus (raw): dialogue_boundary
    → ProcessingAgent.process()
    → Трекинг: agent_reasoning
    → ProcessingAgent выполняет action
    → EventBus (processed): entity_updated
    → Storage: save_entity (через TaskRepository и др.)
```

### 8.2 От системы к пользователю (уведомления)

```
EventBus (raw/processed) → ProcessingAgent.process()
    → [агент решает: уведомить User-B]
    → ProcessingResult.notifications = [...]
    → EventBus (processed): notification_generated
    → NotifyAgent.on_processing_notification()
    → [проверка дубликатов через NotificationLogRepository]
    → DialogueAgent: доставить в диалоге или инициировать новый
    → Трекинг: notification_sent
    → Storage: save_notification_log
```

### 8.3 Между пользователями (через агента)

```
User-A → DialogueAgent.on_message()
    → EventBus (raw): dialogue_boundary
    → ProcessingAgent (TaskManager).process()
    → [TaskManager: извлек задачу, нужно уведомить User-B]
    → ProcessingResult.notifications = [Notification(to_user='User-B', ...)]
    → EventBus (processed): notification_generated
    → NotifyAgent.on_processing_notification()
    → DialogueAgent: доставить User-B
    → User-B получает уведомление
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
