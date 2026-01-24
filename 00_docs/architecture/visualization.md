# Архитектура визуализации (VS UI)

**Дата:** 2025-01-24
**Статус:** Требования и гипотезы для архитектора

---

## 1. Назначение и цели

### 1.1 Зачем нужна визуализация

**Проблема из прошлого опыта:**
> "Я не мог показать людям, что происходит внутри, и поэтому они не понимали и не имели мотивации с этим работать."

**Цель:**
- Наглядно показать что происходит в системе
- Дать людям понимание работы системы
- Создать мотивацию использования через прозрачность

### 1.2 Приоритеты

**Критично:**
- **Наглядность** — должно быть понятно "что происходит"
- **Timeline** — графическое отображение событий во времени
- **Swimlanes** — дорожки для разделения сущностей

**Важно:**
- **Agent reasoning** — показать что думают агенты (SGR traces)
- **User context** — детализация по клику

**Опционально:**
- Графы связей
- Анимированные демо

---

## 2. Технические вводные

### 2.1 Backend API

**Коммуникация:** Polling (простота)
```python
GET /api/timeline?since=2025-01-24T10:00:00

Response:
{
    "events": [
        {
            "timestamp": "2025-01-24T10:15:30",
            "type": "message_received",
            "user_id": "user-1",
            "data": {"content": "Нужно сделать отчет к пятнице"}
        },
        {
            "timestamp": "2025-01-24T10:16:00",
            "type": "dialogue_boundary",
            "user_id": "user-1",
            "reason": "timeout"
        },
        {
            "timestamp": "2025-01-24T10:16:05",
            "type": "agent_reasoning",
            "agent_id": "TaskManager",
            "data": {
                "reasoning": "Анализирую сообщение...",
                "decision": "создать задачу",
                "arguments": {...}
            }
        },
        {
            "timestamp": "2025-01-24T10:16:10",
            "type": "notification_sent",
            "from_user": "user-1",
            "to_user": "user-2",
            "source_agent": "TaskManager"
        }
    ]
}
```

**Задержка:** 1+ секунда — норма, real-time не требуется

### 2.2 DataSource Backend

**Гибридный подход:**
- Прямой трекинг (events.track) — для событий, которые не в основном storage
- Извлечение из storage — для основных данных

```python
class VSDataSource:
    async def get_timeline(self, filter):
        tracked = await self.tracking_storage.get_events(filter)
        extracted = await self.extractor.extract_from_main_storage(filter)
        return self.merge(tracked, extracted)

    async def get_user_context(self, user_id: str):
        """Детализация пользователя"""
        return {
            'messages': await self.storage.get_messages(user_id),
            'profile': await self.storage.get_user_profile(user_id),
            'delivered_notifications': await self.storage.get_notifications_log(user_id)
        }

    async def get_agent_reasoning(self, agent_id: str):
        """Reasoning trace агента"""
        return await self.storage.get_agent_conversation(agent_id)
```

### 2.3 Event Types

**Базовые типы событий:**
```python
# Диалог
message_received          # Пользователь отправил сообщение
message_sent              # Ассистент ответил
dialogue_boundary         # Диалог завершен

# Обработка
agent_reasoning           # Reasoning фаза агента
agent_processing          # Агент обрабатывает данные

# Уведомления
notification_generated    # Агент решил уведомить
notification_sent         # Уведомление доставлено

# Контекст
user_context_updated      # Обновился контекст пользователя
agent_state_changed       # Изменилось состояние агента
```

---

## 3. Требования к фронтенду

### 3.1 Критерии выбора стека

1. **Наглядность** — результат должен выглядеть убедительно
2. **Простота разработки** — не перегружать сложностью
3. **Timeline + swimlanes** — должны быть легко реализуемы

### 3.2 Библиотеки для изучения

**Timeline libraries:**
- **Vis.js Timeline** — JavaScript библиотека для timeline
- **Observable Plot** — для визуализации данных
- **D3.js** — мощная, но сложная

**Graph libraries:**
- **React Flow** — node-based графы
- **Cytoscape.js** — графы и network diagrams
- **Vis.js Network** — network visualization

**Best practices из похожих систем:**
- **Datadog** — trace view (swimlanes + timeline)
- **Langfuse** — LLM observability
- **Arize Phoenix** — AI tracing
- **Jaeger** — distributed tracing

---

## 4. Views (экраны/виды)

### 4.1 Timeline View — **КРИТИЧНО**

**Назначение:** Показать события во времени графически.

**Требования:**
- **НЕ текстовый список** — именно графический timeline
- Горизонтальная ось — время
- Позиция на оси = момент события

**Базовая версия:**
```
Время →  10:15    10:16    10:17
          |        |        |
User-A  [msg]────────[boundary]
                          ↓
TaskMgr                  [reasoning][processing]
                          ↓
User-B                              [notify]
```

**Улучшенная версия (swimlanes):**
- Дорожки по пользователям
- Дорожки по агентам
- Дорожки по объектам (задачам)

### 4.2 Swimlanes View — **КРИТИЧНО**

**Назначение:** Разделение событий по сущностям на дорожки.

**Варианты swimlanes:**

**Вариант A: По пользователям**
```
User-A  [msg]────────[boundary]───────────────>
                                ↓
TaskMgr                  [reasoning][processing]
                                ↓
User-B                              [notify]──>
```

**Вариант B: По объектам**
```
Task-123 [created]────────[assigned]────────[completed]
                    ↓             ↓
User-A       [mentioned]                   [closed]
User-B                     [notified]
```

**Вариант C: Гибридный**
- Пользователи слева/справа
- Агенты в центре
- Объекты как отдельные дорожки

**Требование:** Возможность переключения между вариантами

### 4.3 User Context View — **ВАЖНО**

**Назначение:** Детализация по конкретному пользователю.

**Триггер:** Клик на пользователя в timeline/swimlanes.

**Данные:**
```
User: Alice

Role: Manager
Current focus:
  - Q1 планы
  - Отчетность

Open dialogue:
  - "Нужно сделать отчет к пятнице" (10:15)

Profile:
  - Communication style: формальная
  - Timezone: UTC+3

Received notifications:
  - From Bob: "Поставка задерживается" (10:20)
```

### 4.4 Agent Reasoning View — **ВАЖНО**

**Назначение:** Показать что думает агент (SGR traces).

**Триггер:** Клик на агенте в swimlanes или отдельный view.

**Данные (SGR format):**
```
Agent: TaskManager
Timestamp: 2025-01-24T10:16:05

Reasoning Phase:
{
  "reasoning": "Анализирую сообщение от User-A...",
  "analysis": {
    "detected_task": "сделать отчет",
    "deadline": "пятница",
    "assignee": "User-A"
  },
  "decision": "создать задачу в базе",
  "selected_tool": "save_task",
  "tool_arguments": {
    "title": "Создать отчет",
    "deadline": "2025-01-31",
    "assignee": "user-1"
  }
}

Action Phase:
✅ Task saved (id: task-456)
```

**Форматирование:**
- Reasoning — expandable/collapsible
- Tool calls — выделены
- Results — зеленый/красный индикатор

### 4.5 Graph View — **ОПЦИОНАЛЬНО**

**Назначение:** Показать связи между сущностями.

**Примеры графов:**
- Кто с кем коммуницирует
- Зависимости задач
- Spread информации

**Библиотеки:** React Flow, Cytoscape.js, D3.js

### 4.6 Demo Flow View — **ОПЦИОНАЛЬНО**

**Назначение:** Анимированная демонстрация для лендинга.

**Требование:** Схватывается за 3-5 секунд.

**Идея:**
- Пользователи по краям
- Event Bus в центре
- Анимированные частицы показывают движение информации

---

## 5. Пожелания и гипотезы из обсуждения

### 5.1 Из обсуждения архитектуры

**Наглядность > Real-time:**
- Задержка 1+ секунда — норма
- Не нужно WebSocket для real-time
- Polling достаточен

**Timeline должен быть графическим:**
- НЕ текстовый список строк
- Позиция на оси = момент времени
- Масштабируемость (zoom in/out)

**Swimlanes могут быть разными:**
- По пользователям
- По объектам
- По агентам
- Возможность переключения

**Детализация — отдельный view:**
- User Context — по клику на пользователя
- Agent Reasoning — по клику на агента
- Не перегружать основной view

### 5.2 Из system_requirements.md (исходный документ)

**VS.timeline (swimlanes):**
- Swimlanes: дорожки по пользователям, DB в центре, время по горизонтали
- Основной вид для понимания механики сервиса

**VS.object:**
- Трассировка конкретного объекта через систему

**VS.user:**
- Срез по пользователю: dialogue buffer, history, delivered

**VS.bus:**
- Текущее состояние Event Bus

**VS.flow (демо):**
- Анимированный граф для демо
- Схватывается за 3-5 секунд

---

## 6. Рекомендации для архитектора VS

### 6.1 С чего начать

1. **Изучить best practices:**
   - Datadog trace view
   - Langfuse UI
   - Jaeger UI

2. **Определить фронтенд-стек:**
   - Критерии: наглядность + простота
   - Библиотеки: Vis.js, D3.js, React Flow

3. **Спроектировать основные views:**
   - Timeline (графический!)
   - Swimlanes (с переключением вариантов)
   - User Context (детализация)
   - Agent Reasoning (SGR traces)

4. **Прототип:**
   - Начать с timeline + swimlanes
   - Добавить dummy данные для отладки
   - Проверить наглядность

### 6.2 Интеграция с backend

**API endpoints:**
```
GET /api/timeline?since={timestamp}
GET /api/user/{user_id}/context
GET /api/agent/{agent_id}/reasoning
GET /api/object/{object_id}/trace
GET /api/bus/state
```

**Data format:**
- Timeline: список событий
- Context: структурированные данные
- Reasoning: SGR conversation trace

### 6.3 Testing

**Тестовые данные:**
- Использовать SIM для генерации
- Разные сценарии (простой, сложный, с ошибками)
- Проверить наглядность на реальных данных

---

## 7. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| Выбор фронтенд-стека | Для архитектора VS |
| Конкретные библиотеки | Изучить Vis.js, D3.js, React Flow |
| Layout timeline | Для архитектора VS |
| Количество swimlanes variants | Начать с 2-3 |
| Граф view | Опционально, позже |

---

## 8. Следующие шаги

1. → **Architect VS:** Детальная архитектура визуализации
2. → **Прототип:** Timeline + swimlanes с dummy данными
3. → **Интеграция:** Подключение к backend API
4. → **Тестирование:** Проверка на реальных данных от SIM

---

**Документ:** `00_docs/architecture/visualization.md`
**Архитектор:** Architect Agent (Sonnet 4.5)
**Дата:** 2025-01-24
