# Data Model

**Версия:** 1.0
**Дата:** 2025-02-07

**Связанные документы:**
- `00_docs/architecture/overview.md` — общая архитектура системы
- `00_docs/architecture/runtime_architecture.md` — сквозные сценарии

---

## 1. Введение

### 1.1. Назначение документа

Документ описывает модель данных Team Assistant — структуры хранения в Storage, форматы сообщений, состояния компонентов.

### 1.2. Сущности в скоупе

| Сущность | Описание |
|----------|----------|
| dialogue_state | Состояние диалога для восстановления buffer |
| messages | Сообщения пользователей и системы |
| events | События для визуализации в VS UI |
| agent_state | Состояния Processing Agents |

---

## 2. dialogue_state

### 2.1. Назначение

Хранит персистентное состояние диалога для восстановления in-memory buffer после перезапуска.

### 2.2. Структура

```python
class DialogueStateRow:
    user_id: str              # PRIMARY KEY
    last_published_message_id: str | null  # id последнего сообщения, отправленного в EventBus
    last_activity: datetime    # время последней активности
    is_active: bool            # активен ли диалог
```

### 2.3. Использование

**Восстановление buffer после перезапуска:**

```python
# Загрузка состояния
state = storage.get_dialogue_state(user_id)

# Восстановление buffer
if state and state.last_published_message_id:
    buffer = storage.get_messages_since(
        user_id,
        since_message_id=state.last_published_message_id
    )
else:
    buffer = []
```

**Обновление при публикации фрагмента:**

```python
# После публикации в EventBus
storage.update_dialogue_state(user_id, {
    "last_published_message_id": last_message_id_in_fragment,
    "last_activity": now()
})
```

---

## 3. messages

### 3.1. Назначение

Хранит все сообщения диалогов: от пользователей, ответы AI, скрытые инструкции.

### 3.2. Структура

```python
class MessageRow:
    id: str                  # UNIQUE, PRIMARY KEY
    user_id: str
    role: str                # 'user' | 'assistant' | 'system'
    content: str             # текст сообщения
    user_metadata: dict | null  # JSON: контекстual данные (дата, время, ...)
    timestamp: datetime
```

### 3.3. Роль (role)

| Значение | Описание |
|----------|----------|
| `user` | Сообщение от пользователя |
| `assistant` | Ответ AI |
| `system` | Системные сообщения (скрытые инструкции) |

### 3.4. Скрытые инструкции

Скрытые инструкции хранятся в messages как обычные записи:

```
[ai:native]
[user:native]
[ai:native]
[user:hidden instruction]  ← role='user', content='[hidden instruction] ...'
[ai:notification]          ← role='assistant'
[user:response]            ← role='user'
```

**Фильтрация при формировании контекста для LLM — зона ответственности LLM-интерфейса, не Storage.**

### 3.5. user_metadata

Контекстual данные, которые включаются в промпт LLM:

```python
user_metadata = {
    "current_date": "2026-02-07",
    "current_time": "14:30",
    "user_timezone": "UTC+3",
    # ... другие метаданные
}
```

При отправке в LLM метаданные присоединяются к content.

---

## 4. events

### 4.1. Назначение

События для визуализации в VS UI. Заполняются через EventTracker.

### 4.2. Структура

```python
class EventRow:
    id: str
    timestamp: datetime
    event_type: str          # тип события (строка)
    source: str              # "user:alice" или "agent:TaskManager"
    payload: dict            # JSON: полезная нагрузка
    links: dict | null       # JSON: связи между событиями
```

### 4.3. event_type

Основные типы (не исчерпывающий список):

| Тип | Описание |
|-----|----------|
| `message_sent` | Сообщение отправлено пользователю |
| `message_received` | Сообщение получено от пользователя |
| `dialogue_fragment_published` | Фрагмент диалога опубликован в EventBus |
| `agent_activity_start` | Агент начал обработку |
| `agent_result` | Агент завершил обработку |
| `notification_generated` | Уведомление сгенерировано |
| `notification_sent` | Уведомление отправлено пользователю |
| `sim_start` / `sim_stop` | Симуляция запущена/остановлена |

**Детализация payload и связей — при реализации VS UI.**

---

## 5. agent_state

### 5.1. Назначение

Хранение состояний Processing Agents в формате key-value.

### 5.2. Структура

```python
class AgentStateRow:
    agent_id: str             # PRIMARY KEY часть 1
    key: str                  # PRIMARY KEY часть 2
    value: blob               # бинарные данные или JSON
    updated_at: datetime
```

### 5.3. Примеры

**TaskManager:**
```
agent_id = "task_manager"
key = "pending_tasks"
value = JSON массив задач
```

**ContextManager:**
```
agent_id = "context_manager:user_123"
key = "context_snapshot"
value = JSON снепшот контекста
```

---

## 6. In-memory состояние DialogueAgent

### 6.1. DialogueState (в памяти)

```python
class DialogueState:
    user_id: str
    buffer: list[Message]      # in-memory накопление
    last_activity: datetime
    is_active: bool
```

### 6.2. Восстановление после перезапуска

```
1. Загрузить DialogueStateRow из Storage
2. Если last_published_message_id существует:
   → Загрузить messages WHERE id > last_published_message_id
   → Заполнить buffer
3. Иначе:
   → buffer = []
```

---

## 7. Индексы

Для MVP (добавляются по мере необходимости):

```sql
-- messages
CREATE INDEX idx_messages_user_time ON messages(user_id, timestamp);

-- events
CREATE INDEX idx_events_timestamp ON events(timestamp);

-- dialogue_state
CREATE INDEX idx_dialogue_state_active ON dialogue_state(is_active) WHERE is_active = true;

-- agent_state
CREATE INDEX idx_agent_state_agent ON agent_state(agent_id);
```

---

## 8. Ограничения MVP

### 8.1. НЕ входит в MVP

- Репликация
- Шардирование
- Кэширование
- Оптимизация запросов

### 8.2. Технические ограничения

- **Масштаб:** < 50 пользователей
- **Storage:** SQLite для разработки
- **Продакшен:** TBD (ADR)

---

**Документ:** `00_docs/architecture/data_model.md`
**Последнее обновление:** 2025-02-07
