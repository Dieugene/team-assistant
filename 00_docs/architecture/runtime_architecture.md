# Runtime Architecture
## Сквозные сценарии работы системы

**Версия:** 1.0
**Дата:** 2025-02-07

**Связанные документы:**
- `00_docs/architecture/overview.md` — общая архитектура системы
- `00_docs/architecture/visualization_architecture.md` — архитектура VS UI

---

## 1. Введение

### 1.1. Назначение документа

Документ описывает сквозные сценарии работы Team Assistant — полные пути обработки сообщений от пользователей до доставки ответов. Сценарии верифицируют архитектуру и демонстрируют взаимодействие компонентов в динамике.

### 1.2. Краткое напоминание

**Компоненты (из overview.md):**
- **DialogueAgent** — ведение диалогов с пользователями
- **ProcessingLayer** — массив Processing Agents
- **ContextAgent** — big picture + доставка уведомлений
- **Event Bus** — шина событий (raw, processed, notification)
- **Storage** — персистентное хранение
- **SIM** — генератор тестовых данных
- **VS UI** — визуализация

### 1.3. Сценарии в скоупе

| Сценарий | Описание | Статус |
|----------|----------|--------|
| A | Обработка входящего сообщения пользователя | MVP |
| B | Таймаут диалога и публикация фрагмента | MVP |
| C | Уведомление от Processing Agent → Пользователь | MVP |
| D | Запуск системы (bootstrap) | MVP |
| E | SIM симуляция | MVP |

---

## 2. Глоссарий

### 2.1. Участники процессов

| Термин | Определение |
|--------|-------------|
| Пользователь | Реальный пользователь или SIM-профиль |
| DialogueAgent | Единый инстанс, управляющий всеми диалогами |
| ProcessingAgent | Любой агент из ProcessingLayer (TaskManager, ContextManager, ...) |
| ContextAgent | Агент big picture, подписанный на notification |
| EventBus | Шина событий с топиками raw, processed, notification |
| Storage | Персистентное хранение |
| VS UI | Визуализационный сервис (polling) |

### 2.2. Артефакты

| Термин | Определение |
|--------|-------------|
| Message | Сообщение от пользователя (текст) |
| DialogueFragment | Накопленные сообщения диалога за сессию |
| BusMessage | Сообщение в Event Bus с топиком, payload, links |
| Notification | Уведомление для доставки пользователю |
| DialogueState | Состояние активного диалога (buffer, last_activity) |

---

## 3. Сценарий A: Обработка входящего сообщения

### 3.1. Описание

**Входные данные:**
- user_id (или SIM-профиль)
- message (текст)

**Ожидаемый результат:**
- Ответ пользователю
- Фиксация сообщений в Storage
- Публикация в Event Bus для Processing Agents

### 3.2. Диаграмма

**Фаза 1: Сохранение и генерация ответа**

```mermaid
sequenceDiagram
    autonumber
    participant User as Пользователь/SIM
    participant DA as DialogueAgent
    participant Storage as Storage

    User->>DA: invoke(user_id, message)
    DA->>Storage: save_message(user_id, message, role=user)
    DA->>DA: Добавить в messages_buffer
    DA->>DA: Генерация ответа через LLM
    DA->>Storage: save_message(user_id, response, role=assistant)
    DA->>DA: Обновить last_activity
    DA-->>User: response
```

**Фаза 2-4: Публикация фрагмента и обработка агентами**

```mermaid
sequenceDiagram
    autonumber
    participant DA as DialogueAgent
    participant EB as Event Bus
    participant PL as ProcessingLayer
    participant PA1 as Agent1
    participant PA2 as Agent2
    participant PA3 as Agent3

    Note over DA: Таймаут истёк или явное завершение

    DA->>DA: Собрать DialogueFragment из buffer
    DA->>EB: publish(raw, DialogueFragment)
    DA->>DA: Очистить buffer для следующей сессии

    EB->>PL: notify_all(raw, DialogueFragment)

    par Параллельно всем агентам
        PL->>PA1: process(raw, DialogueFragment)
    and
        PL->>PA2: process(raw, DialogueFragment)
    and
        PL->>PA3: process(raw, DialogueFragment)
    end

    Note over PA1,PA3: Агенты публикуют результаты

    PA1->>EB: publish(processed, result)
    PA2->>EB: publish(notification, notification)
    PA3->>EB: publish(processed, result)
```

### 3.3. Фазы сценария

| Фаза | Описание | Артефакты |
|------|----------|-----------|
| 1 | Сохранение и генерация ответа | Message в Storage, обновление DialogueState |
| 2 | Публикация фрагмента | BusMessage(raw, DialogueFragment) |
| 3 | Обработка агентами | Вызов process() для всех Processing Agents |
| 4 | Результаты обработки | BusMessage(processed), BusMessage(notification) |

---

## 4. Сценарий B: Таймаут диалога

### 4.1. Описание

**Предусловия:**
- Активный диалог с пользователем (есть messages_buffer)
- Время неактивности > timeout_minutes

**Триггер:**
- Периодическая проверка check_timeouts()

**Ожидаемый результат:**
- Фрагмент диалога опубликован в Event Bus
- Buffer очищен для следующей сессии

### 4.2. Диаграмма

**Фаза 1: Триггер проверки таймаутов**

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as Scheduler / Timer
    participant DA as DialogueAgent
    participant Storage as Storage

    Scheduler->>DA: check_timeouts(timeout_minutes, current_timestamp)
    DA->>Storage: get_all_active_dialogues()
    Storage-->>DA: list[DialogueState]
```

**Фаза 2: Обработка истекших диалогов**

```mermaid
sequenceDiagram
    autonumber
    participant DA as DialogueAgent
    participant Storage as Storage
    participant EB as Event Bus
    participant PL as ProcessingLayer

    Note over DA: Для каждого диалога с истёкшим таймаутом

    DA->>DA: Проверить: (current - last_activity) > timeout
    DA->>DA: Собрать DialogueFragment из buffer
    DA->>EB: publish(raw, DialogueFragment)
    DA->>Storage: save_dialogue_fragment(user_id, fragment)
    DA->>DA: Очистить buffer, обновить состояние

    EB->>PL: notify_all(raw, DialogueFragment)
    Note over PL: Агенты обрабатывают параллельно

    DA-->>DA: Добавить в expired_dialogue_ids
```

### 4.3. Параметры

| Параметр | Описание | Значение (по умолчанию) |
|----------|----------|-------------------------|
| timeout_minutes | Время неактивности для фиксации фрагмента | 30 (настраиваемый) |
| check_interval | Периодичность проверки | 60 секунд (настраиваемый) |

---

## 5. Сценарий C: Уведомление от Processing Agent

### 5.1. Описание

**Предусловия:**
- Processing Agent опубликовал notification в Event Bus
- ContextAgent подписан на топик notification

**Входные данные:**
- BusMessage(topic=notification, payload={to_user, message, context})

**Ожидаемый результат:**
- Пользователь получает уведомление через DialogueAgent

### 5.2. Диаграмма

**Фаза 1: Публикация уведомления и анализ ContextAgent**

```mermaid
sequenceDiagram
    autonumber
    participant PA as ProcessingAgent
    participant EB as Event Bus
    participant CA as ContextAgent

    PA->>EB: publish(notification, NotificationPayload)
    EB->>CA: notify(notification, NotificationPayload)

    Note over CA: Анализ: все notifications,<br/>история диалога, другие события
    CA->>CA: Решение: доставлять ли, как формулировать
```

**Фаза 2: Доставка пользователю (если оправдана)**

```mermaid
sequenceDiagram
    autonumber
    participant CA as ContextAgent
    participant DA as DialogueAgent
    participant Storage as Storage
    participant User as Пользователь

    Note over CA: Решение: доставить

    CA->>DA: invoke(user_id, notification_message)
    DA->>Storage: save_message(user_id, notification, role=assistant)
    DA-->>User: notification_message
```

**Фаза 3: Визуализация**

```mermaid
sequenceDiagram
    autonumber
    participant EB as Event Bus
    participant VS as VS UI

    EB->>VS: event_store(notification_sent)
    Note over VS: Отображается в Timeline
```

### 5.3. Логика ContextAgent

**Вход:**
- Все notification события от разных Processing Agents
- История диалога с пользователем
- Другие события в Event Bus

**Решение:**
- Доставлять ли уведомление
- Как формулировать (перефразирование)
- Когда доставить (немедленно / отложенно)

**Выход:**
- invoke(user_id, message) — доставка
- ignore — пропуск

---

## 6. Сценарий D: Запуск системы (Bootstrap)

### 6.1. Описание

**Входные данные:**
- Команда запуска системы

**Ожидаемый результат:**
- Все компоненты инициализированы
- Processing Agents зарегистрированы
- Система готова к работе

### 6.2. Диаграмма

**Фаза 1: Инициализация инфраструктуры**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant Storage as Storage
    participant EB as Event Bus

    Bootstrap->>Storage: initialize()
    Storage-->>Bootstrap: ready
    Bootstrap->>EB: initialize(storage)
    EB-->>Bootstrap: ready
```

**Фаза 2: Регистрация Processing Agents**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant PL as ProcessingLayer
    participant PA as ProcessingAgent
    participant Storage as Storage

    loop Для каждого агента
        Bootstrap->>PL: register(agent)
        PL->>PA: start(storage, event_bus, llm_provider)
        PA->>Storage: restore_state(agent_name) ~если есть~
        PA-->>PL: ready
    end
    PL-->>Bootstrap: all_agents_ready
```

**Фаза 3: Запуск диалоговой системы**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant CA as ContextAgent
    participant DA as DialogueAgent
    participant EB as Event Bus
    participant Storage as Storage

    Bootstrap->>CA: start(event_bus, dialogue_agent)
    CA->>EB: subscribe(notification, handler)
    CA-->>Bootstrap: ready

    Bootstrap->>DA: start(storage, llm_provider)
    DA->>Storage: get_active_dialogues() ~для recovery~
    DA-->>Bootstrap: ready
```

**Фаза 4: Запуск VS UI (опционально)**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant VS as VS UI

    Bootstrap->>VS: start(storage, event_bus)
    VS-->>Bootstrap: ready (polling started)
```

### 6.3. Порядок зависимостей

| Порядок | Компонент | Зависимости |
|---------|-----------|-------------|
| 1 | Storage | — |
| 2 | Event Bus | Storage |
| 3 | Processing Agents | Storage, Event Bus |
| 4 | ContextAgent | Event Bus, DialogueAgent (ref) |
| 5 | DialogueAgent | Storage, LLM Provider |
| 6 | VS UI | Storage, Event Bus |

---

## 7. Сценарий E: SIM симуляция

### 7.1. Описание

**Входные данные:**
- Команда start SIM

**Ожидаемый результат:**
- SIM генерирует сообщения от виртуальных пользователей
- Система обрабатывает как реальные сообщения

### 7.2. Диаграмма

```mermaid
sequenceDiagram
    autonumber
    participant VS as VS UI Controls
    participant SIM as SIM Engine
    participant Profiles as SIM Profiles
    participant DA as DialogueAgent
    participant Storage as Storage

    VS->>SIM: start()

    loop Генерация событий
        SIM->>Profiles: get_next_event()
        Profiles-->>SIM: (profile, scenario_trigger)

        SIM->>SIM: profile + trigger → message
        Note over SIM: Генерация:<br/>≥2-3 факта, эмоциональная окраска

        SIM->>DA: invoke(profile.user_id, message)
        DA->>Storage: save_message(user_id, message)
        DA-->>SIM: response

        opt Ответ нужно сохранить
            SIM->>Storage: save_sim_response(profile.user_id, response)
        end
    end

    VS->>SIM: stop()
    SIM-->>VS: stopped
```

### 7.3. Компоненты SIM

| Компонент | Описание |
|-----------|----------|
| SIM.profiles | Профили виртуальных пользователей (роль, характер, зона ответственности) |
| SIM.scenario | События внешнего мира как триггеры |
| SIM.engine | Генератор: профиль + событие → сообщение |

---

## 8. Graceful Shutdown

### 8.1. Описание

**Триггеры:**
- SIGTERM / SIGINT
- Критическая ошибка (опционально)

**Ожидаемый результат:**
- Активные диалогы корректно завершены
- Состояния сохранены
- Ресурсы освобождены

### 8.2. Диаграмма

**Фаза 1: Прекратить прием новых сообщений**

```mermaid
sequenceDiagram
    autonumber
    participant Signal as OS Signal
    participant Bootstrap as Bootstrap
    participant DA as DialogueAgent

    Signal->>Bootstrap: SIGTERM/SIGINT
    Bootstrap->>DA: stop_accepting_new()
    DA-->>Bootstrap: accepting_stopped
```

**Фаза 2: Завершить активные диалоги**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant DA as DialogueAgent
    participant Storage as Storage

    Bootstrap->>DA: wait_active_dialogues(timeout)

    loop Активные диалоги
        DA->>DA: Завершить или зафиксировать фрагмент
        DA->>Storage: save_dialogue_fragment()
    end

    DA-->>Bootstrap: all_dialogues_closed
```

**Фаза 3: Остановить агенты**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant PL as ProcessingLayer
    participant PA as ProcessingAgent
    participant Storage as Storage

    loop Для каждого агента
        Bootstrap->>PL: stop_agent(agent)
        PL->>PA: stop()
        PA->>Storage: save_state(agent_state)
        PA-->>PL: stopped
    end

    PL-->>Bootstrap: all_agents_stopped
```

**Фаза 4: Завершение работы**

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant EB as Event Bus
    participant Storage as Storage

    Bootstrap->>EB: stop()
    Bootstrap->>Storage: close_connections()
    Storage-->>Bootstrap: closed

    Note over Bootstrap: System terminated
```

### 8.3. Параметры

| Параметр | Описание | Значение (по умолчанию) |
|----------|----------|-------------------------|
| dialogue_timeout | Макс. время ожидания завершения диалогов | 10 секунд |
| agent_stop_timeout | Макс. время ожидания остановки агентов | 5 секунд |

---

## 9. Recovery после crash

### 9.1. Описание

**Предусловия:**
- Система запускается после неожиданного завершения

**Ожидаемый результат:**
- Состояния компонентов восстановлены
- Активные диалоги могут быть продолжены

### 9.2. Диаграмма

```mermaid
sequenceDiagram
    autonumber
    participant Bootstrap as Bootstrap
    participant Storage as Storage
    participant PA as ProcessingAgent
    participant DA as DialogueAgent

    rect rgb(240, 248, 255)
        Note over Bootstrap,PA: Фаза 1: Восстановление агентов
        loop Для каждого агента
            Bootstrap->>Storage: get_last_snapshot(agent_name)
            Storage-->>PA: agent_state or null

            opt snapshot существует
                PA->>PA: restore_state(agent_state)
            end
        end
    end

    rect rgb(255, 245, 240)
        Note over Bootstrap,DA: Фаза 2: Восстановление диалогов
        Bootstrap->>Storage: get_active_dialogues()
        Storage-->>DA: list[DialogueState]

        loop Для каждого диалога
            DA->>Storage: get_last_messages(user_id, limit=N)
            Storage-->>DA: messages[]
            DA->>DA: Восстановить DialogueState
        end
    end

    Bootstrap->>Storage: publish(system_start, {recovered: true})
```

---

## 10. Сводная таблица сценариев

| Сценарий | Вход | Выход | Статус |
|----------|------|-------|--------|
| A | user_id + message | Ответ + события в Event Bus | MVP |
| B | Таймаут диалога | DialogueFragment в raw | MVP |
| C | Notification от агента | Доставка пользователю | MVP |
| D | Команда запуска | Система готова | MVP |
| E | Start SIM | Симуляция сообщений | MVP |
| Shutdown | SIGTERM | Graceful shutdown | MVP |
| Recovery | Запуск после crash | Состояния восстановлены | MVP |

---

**Документ:** `00_docs/architecture/runtime_architecture.md`
**Последнее обновление:** 2025-02-07
