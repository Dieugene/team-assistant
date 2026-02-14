# Decision 001: Хранение SGR conversations в agent_state

**Дата:** 2025-02-07
**Статус:** Принято

---

## Контекст

Tech Lead при планировании реализации Storage обнаружил несоответствие:

- В `overview.md` секция 3.4 описывает сущность `agent_conversations` для хранения историй диалогов processing agents (SGR traces)
- В `data_model.md` этой сущности нет — есть только `agent_state` (key-value хранилище)

Проблема: структура SGR reasoning trace — вложенная (шаги, фазы, actions, results). Помещение её в плоскую таблицу потеряет структуру или требует сложной нормализации.

---

## Решение

Убрать сущность `agent_conversations` из Storage.

SGR conversation traces хранить в `agent_state` как JSON:

```
agent_state:
- agent_id: str           -- например, "task_manager" или "context_manager:user_123"
- key: str                -- например, "conversation", "last_trace"
- value: str (JSON)       -- полная SGR структура
- updated_at: datetime
```

**Пример значения:**
```json
{
  "agent_id": "task_manager",
  "conversation": {
    "steps": [
      {
        "phase": "reasoning",
        "content": {...}
      },
      {
        "phase": "action",
        "content": {...}
      }
    ],
    "final_action": "create_task",
    "final_result": {...}
  }
}
```

---

## Обоснование

1. **Структура данных:** SGR traces — вложенная структура, не подходящая для плоской таблицы
2. **Назначение:** Используются только для отладки и визуализации reasoning в VS UI
3. **Изоляция:** Agent conversation — внутреннее дело агента, не смешивается с user messages
4. **Упрощение:** Одна сущность `agent_state` вместо двух (`agent_conversations` + `agent_data`)

---

## Последствия

### Для overview.md

**Секция 3.4 Storage** — убрать `agent_conversations` из списка сущностей.

**Было:**
| Сущность | Описание |
|----------|----------|
| `messages` | Сообщения пользователей (диалоги) |
| `events` | События из Event Bus (для VS UI и replay) |
| `agent_conversations` | Истории диалогов processing agents (SGR) |
| `agent_data` | Рабочие данные для processing agents |

**Станет:**
| Сущность | Описание |
|----------|----------|
| `messages` | Сообщения пользователей (диалоги) |
| `events` | События из Event Bus (для VS UI и replay) |
| `agent_state` | Состояния processing agents (key-value, включая conversations) |

### Для реализации

- Один репозиторий `IAgentStateRepository` вместо двух
- Value хранится как JSON (TEXT в SQLite)
- При восстановлении агента — десериализация JSON

---

## Связанные документы

- `00_docs/architecture/overview.md` — секция 3.4 (требует обновления)
- `00_docs/architecture/data_model.md` — секция 5 (agent_state)
