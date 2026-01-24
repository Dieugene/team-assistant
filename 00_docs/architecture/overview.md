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
│  │                                                              │ │
│  │  ┌──────────────────┐        ┌──────────────────┐          │ │
│  │  │ DialogueAgent    │        │ ProcessingAgent  │          │ │
│  │  │ (publishes       │◄───────┤ (subscribes to   │          │ │
│  │  │  dialogue_boundary)│      │  dialogue_boundary)│        │ │
│  │  └──────────────────┘        └──────────────────┘          │ │
│  │                                                              │ │
│  │  ┌──────────────────┐        ┌──────────────────┐          │ │
│  │  │ ProcessingAgent  │───────►│ DialogueAgent    │          │ │
│  │  │ (publishes       │        │ (subscribes to   │          │ │
│  │  │  notifications)  │        │  notifications)  │          │ │
│  │  └──────────────────┘        └──────────────────┘          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↕                                     │
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

**Event Bus:**
- Шина событий для коммуникации между модулями
- pub/sub с персистентностью в Storage

**Инфраструктурный уровень:**
- Storage — персистентное хранение всех данных

---

## 3. Детальное описание модулей

### 3.1 Dialogue & Notify Agents (единая диалоговая система)

**Назначение:** AI-ассистент для каждого пользователя, который ведет диалог и доставляет уведомления.

#### 3.1.1 DialogueAgent

**Единый инстанс:**
- Один DialogueAgent управляет всеми диалогами одновременно
- Каждый диалог идентифицируется по `user_id`
- Агент хранит состояние активных диалогов в памяти

**Точки активации:**

**1. Входящее сообщение от пользователя — `invoke(user_id, message)`**
- Основной триггер для диалога
- Агент генерирует ответ через LLM
- Сохраняет сообщения в Storage
- При завершении диалога публикует `dialogue_boundary` в Event Bus

**2. Проверка таймаутов — `check_timeouts(timeout_minutes, timestamp)`**
- Вызывается периодически внешним scheduler или внутри агента
- Загружает истории всех активных диалогов
- Для каждого диалога проверяет время последней коммуникации
- Если время > `timeout_minutes`:
  - Публикует `dialogue_boundary` с reason="timeout" в Event Bus
  - Обновляет состояние буфера диалога для следующей сессии
- Возвращает список диалогов, превышающих таймаут

**3. Проверка Event Bus — `check_event_bus(after_timestamp)`**
- Вызывается периодически или по триггеру
- Читает все события из Event Bus с момента `after_timestamp`
- Пример события от TaskManager: "У пользователя X появились задачи Y, Z"
- Агент анализирует события и решает: какому пользователю что сообщить
- Инициирует диалог proactive через `invoke(user_id, message)`

#### 3.1.2 NotifyAgent

**Соотношение с DialogueAgent:**
- NotifyAgent НЕ дублирует функциональность DialogueAgent
- NotifyAgent — это **фильтр и роутер** уведомлений от ProcessingAgents
- DialogueAgent — это **интерфейс к пользователю** (генерация ответов, ведение диалога)

**Поток уведомлений:**
```
ProcessingAgent → Event Bus: "уведомить User-B о X"
    → NotifyAgent подписан на такие события
    → NotifyAgent проверяет: не дубликат ли это? (см. ниже)
    → NotifyAgent вызывает DialogueAgent.invoke(user_id, notification_message)
    → DialogueAgent ведет диалог с пользователем
```

**Проверка дубликатов — сложная LLM-операция:**
- Отдельные сообщения могут содержать элементы, частично упомянутые в других сообщениях
- Что-то могло быть упомянуто ранее и уже попало в историю диалога
- Проверка выполняется LLM на этапе инициации диалога с учетом **суммарного контекста**:
  - История предыдущих уведомлений этому пользователю
  - История диалога с этим пользователем
  - Текущее уведомление
- LLM решает: это дубликат / частичное дублирование / новая информация
- Не изолированная проверка двух строк, а анализ контекста

---

### 3.2 Processing Agents (подключаемые модули)

**Назначение:** Обработка данных из Event Bus, управление сущностями, принятие решений о доставке.

**Архитектурные принципы:**
- **Подключаемые через интерфейс** — единый контракт для всех агентов
- Каждый агент имеет свой **state** и **memory** (см. Storage раздел)
- Все используют LLM (SGR Agent Core или другие подходы)
- **Агенты сами решают** кому что доставить (помечают recipients)

**Интерфейс:**
- `start() / stop()` — lifecycle методы
- `process(message, context) -> ProcessingResult` — обработка события
- `get_state() / save_state()` — управление состоянием (опционально)

**ProcessingResult содержит:**
- `entities` — извлеченные/обновленные сущности
- `notifications` — кому что доставить (агент сам помечает recipients)
- `reasoning` — reasoning trace для VS UI

**Примеры агентов:**

**TaskManager:**
- Отслеживает задачи и сроки
- Ведет базу задач (создание, обновление, закрытие)
- Отправляет уведомления о приближении сроков

**ContextManager:**
- Отслеживает движение информации между пользователями
- Определяет что из входящих данных может быть полезно конкретному пользователю
- Анализирует контекст каждого пользователя (текущий фокус, роль)

**Развитие системы агентов:**
- Сначала: рамочная система с интерфейсом `IProcessingAgent`
- Когда рамочная система готова: отдельная ветка разработки агентов
- Tech Lead НЕ занимается составом агентов

---

### 3.3 Event Bus

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

**Архитектурный подход:**
- **Универсальный низкоуровневый интерфейс** — IStorage не зависит от бизнес-логики
- **Repository pattern** — бизнес-модули используют типизированные репозитории поверх Storage

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

**State vs Memory:**

| Понятие | Описание | Где хранится | Когда сбрасывается |
|---------|----------|--------------|-------------------|
| **State** | Текущее состояние объекта на момент времени | Storage (персистентно) | При обновлении состояния |
| **Memory** | История предыдущих состояний и действий | Storage (персистентно) | Обычно никогда (архив) |
| **In-memory cache** | Кэш в RAM для быстрого доступа | RAM процесса | При перезапуске процесса |

**Пример для ProcessingAgent:**
- **State:** текущий счетчик, последний обработанный timestamp, флаги
- **Memory:** SGR conversation history (reasoning + actions)
- **In-memory:** кэш загруженного state для текущей сессии

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
- Сохраняются в Storage для replay

**Event Tracking (наблюдаемость):**
- События для визуализации в VS UI
- Пример: `message_received`, `agent_reasoning`, `notification_sent`
- Сохраняются отдельно для timeline

**Разница на примере dialogue_boundary:**
- Event Bus: сигнал для ProcessingAgents (содержит сообщения)
- Tracking: событие для timeline (содержит reason, user_id)

### 4.2 Гибридный подход VS DataSource

**Прямой трекинг** — для событий, которых нет в основном storage:
- `agent_reasoning`
- `notification_generated`
- `dialogue_boundary_complete`

**Извлечение из storage** — для основных данных:
- Messages → конвертируем в timeline events
- Event Bus events → добавляем в timeline

### 4.3 Event Tracker

Аналог Amplitude SDK — фиксирует события для визуализации.

**Основные события:**
- `message_received / message_sent`
- `dialogue_boundary_complete`
- `agent_reasoning`
- `notification_generated / notification_sent`

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

### 6.2 Использование в проекте

**Processing Agents на базе SGR:**
- Reasoning: анализ через LLM
- Action: сохранение/обновление в базе через tool
- Reasoning trace возвращается в `ProcessingResult`

**Conversation storage:**
- SGR хранит conversation в памяти агента
- Наш storage сохраняет для персистентности
- Кто вызывает сохранение — на усмотрение Tech Lead (периодически, после action, при stop)

**Reasoning traces для VS UI:**
- Reasoning phase возвращает структуру
- Сохраняется для визуализации через events.track()
- Где вызывается — внутри process() или через callback — на усмотрение Tech Lead

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
User → DialogueAgent
    → Storage: сообщения
    → [dialogue complete] → EventBus (raw)
    → ProcessingAgent
    → EventBus (processed) → Storage
```

### 8.2 От системы к пользователю (уведомления)

```
EventBus (raw/processed) → ProcessingAgent
    → [агент решил: уведомить User-B]
    → EventBus (processed)
    → NotifyAgent
    → DialogueAgent → User-B
```

### 8.3 Между пользователями

```
User-A → DialogueAgent → EventBus (raw)
    → ProcessingAgent (TaskManager)
    → [нужно уведомить User-B]
    → EventBus (processed)
    → NotifyAgent → DialogueAgent → User-B
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
