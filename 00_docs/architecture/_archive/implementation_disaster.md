# Implementation Disaster

**Дата:** 2025-02-07
**Статус:** Архитектура требует пересмотра

---

## Хронология диалога

**Цель:** Tech Lead должен создать implementation plan, backlog и первые задачи для команды.

**Процесс:**
1. Изучение архитектурных документов
2. Попытка группировки компонентов в блоки
3. Обнаружение противоречий
4. Множественные вопросы пользователю
5. Эскалация архитектору (agent_conversations)
6. Окончательное понимание: документы несогласованы

---

## Выявленные проблемы

### 1. Смешение понятий EventBus и EventTracker

**Термин "events" используется в трех разных смыслах:**

| Документ | Значение "events" |
|----------|-------------------|
| overview.md секция 3.4 | "События из Event Bus (для VS UI и replay)" |
| data_model.md секция 4 | "События для визуализации в VS UI. Заполняются через EventTracker" |
| runtime_architecture.md секция 10.2 | EventTracker фиксирует события в Storage.events |
| visualization_architecture.md секция 7.2 | DialogueFragmentPublished → EventBus → EventTracker → Storage.events |

**Проблема:** Event Bus тоже сохраняет себя в Storage. Event Tracker тоже сохраняется в Storage.
- Это одна таблица `events` или две?
- Если одна — как различить BusMessage от TimelineEvent?
- Если две — зачем тогда в overview.md написано "События из Event Bus (для VS UI и replay)"?

**Цитата из runtime_architecture.md секция 10.2:**
```
Поток данных:
Любой компонент → EventBus → EventTracker → Storage.events
VS UI (polling) → GET /api/timeline → Storage.events → Timeline
```

Event Tracker подписан на EventBus. Значит EventBus генерирует события, EventTracker их трансформирует в TimelineEvent.

Но где тогда хранятся оригинальные BusMessage из EventBus? В той же таблице? В отдельной?

---

### 2. Структура BusMessage не определена

**Из overview.md секция 3.3:**
```python
class IEventBus(ABC):
    async def publish(self, topic: Topic, message: BusMessage) -> MessageId
```

**Вопросы:**
- Какова структура BusMessage?
- Какие поля у topic? ("raw", "processed", "notification" — это enum или строки?)
- Какова структура payload в BusMessage?
- Как BusMessage отличается от TimelineEvent?

**Из runtime_architecture.md:**
```
| BusMessage | Сообщение в Event Bus с топиком, payload, links |
```

Но полный интерфейс не приведен.

---

### 3. DialogueFragment — неопределенная сущность

**Из runtime_architecture.md:**
```
| DialogueFragment | Фрагмент диалога для обработки Processing Agents |
```

**Вопросы:**
- Какова структура DialogueFragment?
- Это список Message? Или отдельная структура?
- Как он преобразуется в BusMessage при publish(raw, DialogueFragment)?
- Как он отображается в TimelineEvent для VS UI?

**Из overview.md секция 3.1.1:**
```
Фиксирует фрагмент диалога
Публикует в Event Bus с пометкой `raw`
```

Но что именно публикуется? Полный буфер? Срез по времени?

---

### 4. agent_conversations — развился через ADR-001, но overview.md не обновлен

**Было в overview.md:**
```
| `agent_conversations` | Истории диалогов processing agents (SGR) |
```

**Не было в data_model.md:** этой сущности нет.

**Решено через ADR-001:** убрать `agent_conversations`, хранить в `agent_state` как JSON.

**Но overview.md до сих пор содержит старую структуру.**

---

### 5. Storage сущности — противоречивый список

**overview.md секция 3.4:**
```
| `messages` | Сообщения пользователей (диалоги) |
| `events` | События из Event Bus (для VS UI и replay) |
| `agent_conversations` | Истории диалогов processing agents (SGR) |
| `agent_data` | Рабочие данные для processing agents |
```

**data_model.md:**
```
| dialogue_state | Состояние диалога для восстановления buffer |
| messages | Сообщения пользователей и системы |
| events | События для визуализации в VS UI |
| agent_state | Состояния Processing Agents |
```

**Противоречия:**
- overview.md: `agent_conversations` vs data_model.md: `agent_state`
- overview.md: `agent_data` vs data_model.md: `agent_state`
- overview.md: нет `dialogue_state` в списке

---

### 6. Event Tracker — неясная ответственность

**Из overview.md секция 4.3:**
```
Event Tracker — аналог Amplitude SDK — фиксирует события для визуализации
```

**Из runtime_architecture.md секция 10.2:**
```
EventTracker подписан на все топики Event Bus
```

**Вопрос:**
Event Tracker — это подписчик EventBus? Или компонент который вызывает напрямую через events.track()?

**Из visualization_architecture.md:**
```
ProcessingAgent → EventBus (agent_activity_start)
    → Event Tracker фиксирует
```

Похоже на подписку. Но как тогда выглядит интерфейс?

---

### 7. Отсутствие контрактов между компонентами

**Пример: DialogueAgent → EventBus**
```
DA->>EB: publish(raw, DialogueFragment)
```

**Проблемы:**
- Структура DialogueFragment не определена
- Как transformation происходит в BusMessage?
- Какие поля обязательные?

**Пример: ProcessingAgent → EventBus**
```
PA1->>EB: publish(processed, result)
PA2->>EB: publish(notification, notification)
```

**Проблемы:**
- `result` — какого типа?
- `notification` — какого типа?
- Они оба BusMessage? Или разные типы payload?

---

### 8. IProcessingAgent интерфейс — неясный lifecycle

**Из overview.md:**
```
Интерфейс:
- start() / stop() — lifecycle методы
- process(message, context) -> ProcessingResult — обработка события
- get_state() / save_state() — управление состоянием (опционально)
```

**Вопрос от пользователя:**
> Поясни, откуда взялись IProcessingAgent.start|stop. Какой у нас интерфейс работы с ними?

**Из runtime_architecture.md секция 6.2:**
```
Bootstrap->>PL: register(agent)
PL->>PA: start(storage, event_bus, llm_provider)
```

**Проблема:** start() принимает параметры. Но в overview.md написано просто "start() / stop()".

Что верно?

---

### 9. LLM Provider Interface — неправильный пример

**Мой предложенный интерфейс:**
```python
class ILLMProvider(ABC):
    async def complete(self, prompt: str, tools: list[Tool] | None = None) -> LLMResponse
```

**Замечание пользователя:**
> Вместо prompt должен быть массив сообщений. Также помимо tools могут быть другие настройки работы...

**Из overview.md секции 5.2 и 6:**
LLM Provider Layer с ретраями... но полный интерфейс не приведен.

SGR Agent Core integration описана, но не как интерфейс.

---

### 10. Users Panel — источник данных неясен

**Из visualization_architecture.md секция 7.1:**
```
SIM Engine → DialogueAgent.invoke()
    → Message stored in Storage
    → Users Panel polling (GET /api/users)
```

Users Panel читает из Storage.messages напрямую.

Но откуда брать last_received? Из тех же messages с фильтром по role='assistant'?

Контракт не определен.

---

### 11. Event Bus persistence — как именно?

**Из overview.md:**
```
Event Bus использует Storage для сохранения событий
```

**Вопросы:**
- Через какой репозиторий? IStorage напрямую? IEventRepository? IBusMessageRepository?
- Какова структура данных для сохранения?
- Отличается ли она от TimelineEvent?

---

### 12. links между событиями — как реализуются?

**Из visualization_architecture.md:**
```typescript
links: {
  triggered_by: string[]
  triggered: string[]
}
```

**Из runtime_architecture.md:**
```
Event B (agent_activity_start) with links.triggered_by = [A.id]
```

**Вопрос:**
Кто устанавливает эти ссылки? Event Bus? Event Tracker? Или компонент который публикует?

Если ProcessingAgent публикует agent_activity_start — откуда он знает ID события dialogue_fragment которое его триггеруло?

---

## Что не хватает в архитектуре

### 1. Единый глоссарий

Каждый термин должен иметь одно значение. Сейчас:
- "events" = BusMessage? TimelineEvent? Или оба?
- "notification" = топик EventBus? Или тип TimelineEvent? Или payload в BusMessage?
- "message" = Message из Storage? Или BusMessage?

### 2. Полные структуры данных

**Нужно определить:**
- BusMessage (поля, типы)
- DialogueFragment (поля, типы)
- Notification (как payload)
- TimelineEvent (уже есть в visualization_architecture.md, но не синхронизировано)

### 3. Четкое разделение ответственности

**EventBus vs EventTracker:**
- EventBus хранит BusMessage (для replay коммуникации между модулями)
- EventTracker хранит TimelineEvent (для VS UI)

Это две разные таблицы или одна? Если разные — как называются?

### 4. Контракты между модулями

**Нужно для каждой пары:**
- Какие данные передаются
- В каком формате
- Какие поля обязательные
- Какие опциональные

### 5. Диаграммы данных с типами

От источника к назначению, с указанием типа данных на каждом шаге.

Пример:
```
DialogueAgent.publish(raw, DialogueFragment)
    → BusMessage(topic="raw", payload={...})
    → EventBus.persist()
    → IEventRepository.save_bus_message(BusMessage)
    → Storage.bus_messages
```

---

## Рекомендация

Архитектуру нужно пересобрать заново с фокусом на:

1. **Четкой терминологии** — один термин = одно значение
2. **Разделении EventBus (коммуникация) и EventTracker (визуализация)** — разные таблицы, разные репозитории
3. **Полных контрактах между компонентами** — структуры данных для всех API
4. **Согласовании всех документов между собой** — update overview.md после ADR-001

---

## Хронология моих ошибок

1. **Предложил ILLMProvider с prompt вместо messages[]** — не прочитал/не понял архитектуру
2. **Сгруппировал Event Tracker только с timeline** — не понял что это для всех панелей VS UI
3. **Предложил разные репозитории для messages и agent_conversations** — не увидел что структуры одинаковые
4. **Не сразу заметил смешение EventBus events и VS UI events**
5. **Создал короткий implementation_disaster** — не собрал весь контекст диалога

**Корневая проблема:** Пытался создать implementation plan не разобравшись в терминах и контрактах.

---

## Следующие шаги

1. Architect пересобирает архитектуру с фокусом на терминах и контрактах
2. Tech Lead заново создает implementation plan после обновления архитектуры
3. Все документы должны быть синхронизированы
