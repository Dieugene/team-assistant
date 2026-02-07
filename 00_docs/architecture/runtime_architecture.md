# Runtime Architecture

**Дата:** 2025-02-07
**Статус:** Архитектура для MVP
**Связанные документы:**
- `00_docs/architecture/overview.md` — общая архитектура системы
- `00_docs/architecture/visualization_architecture.md` — архитектура VS UI

---

## 1. Модель выполнения

### 1.1 Async/Await

**Основная модель:** Python asyncio (async/await)

**Обоснование:**
- Естественная модель для I/O-интенсивной работы (LLM calls, storage)
- Совместимость с FastAPI
- Возможность параллельного выполнения Processing Agents

### 1.2 Event Loop

**Одиночный event loop** для всех компонентов системы.

**Следствия:**
- Blocking операции блокируют всю систему
- CPU-интенсивные задачи должны выноситься в процессы/потоки (если появятся)

### 1.3 Конкурентность Processing Agents

**Модель:** Параллельная обработка событий

```
Event Bus publish(event)
    → [Agent1.process(), Agent2.process(), Agent3.process()] запускаются параллельно
    → Каждый агент работает независимо
    → Результаты публикуются в Event Bus по готовности
```

**Ограничения:**
- Агенты не должны разделять mutable state (кроме Storage)
- Storage обеспечивает транзакционность

---

## 2. Lifecycle Management

### 2.1 Последовательность запуска

```
1. Storage
   ↓
2. Event Bus
   ↓
3. Processing Agents (регистрация)
   ↓
4. ContextAgent
   ↓
5. DialogueAgent
   ↓
6. SIM (опционально)
```

**Ответственный:** Application bootstrap (модуль инициализации)

### 2.2 Lifecycle методы

**Интерфейс IStoppable:**

```python
class IStoppable(ABC):
    async def start(self) -> None:
        """Запуск компонента"""

    async def stop(self) -> None:
        """Остановка компонента, освобождение ресурсов"""
```

**Реализуют:**
- Processing Agents
- ContextAgent
- DialogueAgent
- SIM

**НЕ реализуют:**
- Storage (SQLite connection management через пул)
- Event Bus (in-memory, остановка вместе с event loop)

### 2.3 Graceful Shutdown

**Последовательность:**

```
1. Перестать принимать новые входящие сообщения
2. Дождаться завершения активных диалогов (timeout)
3. Остановить Processing Agents
4. Сохранить состояния (agent state, conversations)
5. Остановить Event Bus
6. Закрыть Storage connections
```

**Триггеры:**
- SIGTERM / SIGINT
- Критическая ошибка (опционально: fallback к сохранению состояния)

---

## 3. State Management

### 3.1 Состояние DialogueAgent

**В памяти (ephemeral):**
- Активные диалоги (user_id → DialogueState)
- Буферы накопленных сообщений

**Персистентность:**
- Все сообщения сохраняются в Storage сразу
- При crash: восстановление состояния из Storage (загрузка последних N сообщений на пользователя)

**DialogueState:**

```python
class DialogueState:
    user_id: str
    messages_buffer: list[Message]      # Накопленные сообщения
    last_activity: datetime             # Для check_timeouts
    is_active: bool
```

### 3.2 Состояние Processing Agents

**In-memory:**
- State агента (рабочие данные: задачи, контексты)

**Персистентность:**
- Агент сохраняет состояние в Storage через периодические snapshots или после каждого действия
- При crash: восстановление из последнего snapshot

**Интерфейс:**

```python
class IProcessingAgent(ABC):
    async def get_state(self) -> dict:
        """Текущее состояние для персистентности"""

    async def restore_state(self, state: dict) -> None:
        """Восстановление состояния"""
```

### 3.3 Recovery после crash

**При запуске системы:**

```
1. Storage загружает last snapshot для каждого Processing Agent
2. Processing Agent.restore_state()
3. DialogueAgent загружает последние сообщения для активных диалогов
4. system_start event публикуется в Event Bus
```

---

## 4. Integration Contracts

### 4.1 Сообщения в Event Bus

**Базовая структура:**

```python
@dataclass
class BusMessage:
    id: str                            # Уникальный ID (UUID)
    timestamp: datetime                 # Время создания
    topic: Topic                       # raw | processed | notification
    source: str                        # источник (agent_name, user_id, system)
    payload: dict                      # Полезная нагрузка (типизирована по теме)
    links: MessageLinks | None = None  # Связи между сообщениями
```

**MessageLinks:**

```python
@dataclass
class MessageLinks:
    triggered_by: list[str]            # ID сообщений которые вызвало это
    correlation_id: str | None = None  # Для трассировки цепочки
```

### 4.2 Топики Event Bus

**Topic: raw**

```python
class DialogueFragmentPayload(TypedDict):
    user_id: str
    messages: list[Message]
    fragment_id: str
```

**Topic: processed**

```python
class ProcessedResultPayload(TypedDict):
    agent_name: str
    input_message_id: str              # ID входящего сообщения
    result_type: str                   # Тип результата
    result_data: dict
```

**Topic: notification**

```python
class NotificationPayload(TypedDict):
    notification_id: str
    to_user: str
    message: str
    source_agent: str
    context: dict | None
```

### 4.3 DialogueAgent.invoke

**Контракт:**

```python
class IDialogueAgent(ABC):
    async def invoke(self, user_id: str, message: str) -> InvokeResult:
        """
        Инициировать диалог с пользователем.

        Args:
            user_id: Идентификатор пользователя
            message: Исходное сообщение (от пользователя или от системы)

        Returns:
            InvokeResult с ответом пользователя (если получен)

        Raises:
            DialogueError: При ошибке диалога
        """
```

**InvokeResult:**

```python
@dataclass
class InvokeResult:
    success: bool
    response: str | None               # Ответ пользователя
    dialogue_completed: bool           # Завершен ли диалог
```

### 4.4 ProcessingAgent.process

**Контракт:**

```python
class IProcessingAgent(ABC):
    async def process(self, message: BusMessage, context: ProcessingContext) -> ProcessingResult:
        """
        Обработать событие из Event Bus.

        Args:
            message: Сообщение из Event Bus
            context: Контекст выполнения (storage, event_bus для публикации)

        Returns:
            ProcessingResult с опциональной публикацией в Event Bus

        Raises:
            ProcessingError: При критической ошибке обработки
        """
```

**ProcessingResult:**

```python
@dataclass
class ProcessingResult:
    success: bool
    publish: list[PublishTarget] | None  # Что публиковать в Event Bus
    reasoning_trace: dict | None         # Для визуализации

@dataclass
class PublishTarget:
    topic: Topic
    payload: dict
    links: MessageLinks | None
```

**ProcessingContext:**

```python
@dataclass
class ProcessingContext:
    storage: IStorage
    event_bus: IEventBus
    llm_provider: ILLMProvider
```

---

## 5. Error Handling

### 5.1 Стратегия в общем виде

**Уровни обработки:**

1. **Component level** — компонент обрабатывает свои ошибки
2. **System level** — логирование, уведомление, continuation

**Принципы:**
- Ошибка в одном Processing Agent не останавливает систему
- Критические ошибки логируются, система пытается продолжить работу
- Персистентность: состояние сохраняется перед критическими операциями

### 5.2 Типы ошибок

**Восстанавливаемые:**
- Временный сбой LLM provider (retry)
- Временный сбой Storage (retry)
- Некорректное сообщение от пользователя (логирование, ответ с ошибкой)

** Невосстанавливаемые:**
- Ошибка конфигурации (shutdown)
- Ошибка схемы данных (ADR required)

### 5.3 Логирование

**Уровни:**
- DEBUG — детальная трассировка (reasoning, internal state)
- INFO — ключевые события (dialogue started, notification sent)
- WARNING — восстанавливаемые ошибки
- ERROR — критические ошибки

**Назначение:**
- Отладка разработки
- Пост-анализ инцидентов
- Опционально: метрики для алертов

---

## 6. Коммуникация с внешним миром

### 6.1 Входящие сообщения

**На MVP:** SIM Engine → DialogueAgent.invoke

**На будущее:**
- Telegram Bot API → DialogueAgent.invoke
- WebSocket → DialogueAgent.invoke
- HTTP API → DialogueAgent.invoke

**Абстракция:** Transport Layer — адаптеры к DialogueAgent

### 6.2 Исходящие сообщения

**На MVP:** DialogueAgent → VS UI (через Storage + polling)

**На будущее:**
- Telegram Bot API (отправка сообщений)
- Push notifications
- Email

---

## 7. Ограничения MVP

### 7.1 Масштаб

- < 50 пользователей
- < 100 активных диалогов одновременно
- < 10 Processing Agents

### 7.2 Производительность

- Latency LLM calls: основной bottleneck
- Storage: SQLite достаточно для MVP
- Event Bus: in-memory, ограничен памятью процесса

### 7.3 Доступность

- Single-node deployment
- Нет HA / failover
- Recovery после crash через сохранение состояния

---

**Документ:** `00_docs/architecture/runtime_architecture.md`
**Последнее обновление:** 2025-02-07
