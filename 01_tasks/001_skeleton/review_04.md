# Ревизия Tech Lead: полная проверка задачи 001 (Review 04)

**Дата:** 2026-02-14
**Автор:** Tech Lead (через субагента-ревьюера)
**Цель:** Полная ревизия перед приёмкой — проверка запускаемости, .gitignore, структуры папок, импортов, тестов.

---

## Критические проблемы (блокируют работу) — 6 шт.

**[C-1] Реальный API-ключ Anthropic закоммичен в репозиторий**
- Где: `02_src/.env`, строка 2
- Что не так: Файл содержит реальный ключ. Ключ в истории коммитов.
- Что нужно сделать:
  1. Немедленно отозвать ключ через консоль Anthropic
  2. Добавить `.env` и `**/.env` в .gitignore
  3. Создать `.env.example` без реальных значений
  4. Очистить ключ из git-истории (BFG / git filter-branch)

**[C-2] Сломанные импорты `from .sim import ISim, Sim` в `core/app.py`**
- Где: `02_src/core/app.py`, строки 7, 8, 15
- Что не так: Внутри `core/` нет пакета `sim`. Пакет `sim` в `02_src/sim/`. ImportError при запуске. Строки 7 и 8 — дубликаты.
- Что нужно сделать: Исправить путь импорта, удалить дубли.

**[C-3] Такая же ошибка импорта sim в `core/app_patch.py`**
- Где: `02_src/core/app_patch.py`, строка 3

**[C-4] Критическая ошибка в `core/api/app.py` — импорт sim + нерабочая логика создания SIM**
- Где: `02_src/core/api/app.py`, строки 60-63
- Что не так: `from .sim import ISim, Sim` — нет пакета; `_db_path.replace('.db', '')` вызывается на объекте Path (не строке).
- Что нужно сделать: Убрать создание SIM из `create_fastapi_app()`. Одна точка входа для SIM — в `main.py`.

**[C-5] Отсутствует `import logging.config`**
- Где: `02_src/core/logging_config.py`, строка 91
- Что не так: `logging.config.dictConfig()` вызывается без импорта `logging.config`. AttributeError.

**[C-6] SQL-схема: индексы создаются ДО таблиц**
- Где: `02_src/core/storage/schema.sql`, строки 10-16
- Что не так: `CREATE INDEX` для `messages`, `trace_events`, `bus_messages` до `CREATE TABLE`. SQL упадёт.
- Что нужно сделать: Переместить `CREATE INDEX` после `CREATE TABLE`.

---

## Важные проблемы (нужно исправить) — 12 шт.

**[I-1] .gitignore не содержит критические паттерны**
- Отсутствуют: `venv/`, `.venv/`, `env/`, `node_modules/`, `__pycache__/`, `*.pyc`, `.env`, `**/.env`, `*.db`, `*.sqlite`, `*.log`, `dist/`, `build/`

**[I-2] Относительные пути к `03_data/` и `04_logs/` — зависят от CWD**
- `02_src/.env:5` — `DATABASE_URL=03_data/team_assistant.db`
- `02_src/core/app.py:42` — `"03_data/team_assistant.db"`
- `02_src/core/storage/storage.py:106` — `"03_data/team_assistant.db"`
- `02_src/core/logging_config.py:55` — `"04_logs/app.log"`
- Нужно: ввести PROJECT_ROOT и строить абсолютные пути.

**[I-3] `conftest.py`: fixture `dialogue_agent` — неправильный порядок аргументов**
- Где: `02_src/tests/conftest.py:62`
- Конструктор принимает `(llm_provider, event_bus, storage, tracker)`, передаётся `(storage, event_bus, tracker, mock_llm)`.

**[I-4] `conftest.py`: fixture `processing_layer` — неполная сигнатура**
- Где: `02_src/tests/conftest.py:73`
- Не хватает `tracker` и `llm_provider`.

**[I-5] Тест `test_event_bus.py` — вызов несуществующего `storage.get_bus_messages()`**
- Где: `02_src/tests/test_event_bus.py:151`

**[I-6] Тесты `test_tracker.py` — вызов несуществующего `tracker.stop()`**
- Где: `02_src/tests/test_tracker.py:91,121,149`

**[I-7] Тесты LLMProvider — неправильный путь патча и sync vs async**
- Где: `02_src/tests/test_llm_provider.py`
- Патчат `core.llm.provider.Anthropic` (не существует), а модуль `core.llm.llm_provider`. Патчат sync `Anthropic` вместо `AsyncAnthropic`.

**[I-8] Маршруты SIM — дублирование префикса**
- Где: `02_src/core/api/routes/control.py:47,61`
- Роутер `prefix="/api/control"` + маршрут `"/api/control/sim/start"` = `/api/control/api/control/sim/start`.
- Исправить на `"/sim/start"` и `"/sim/stop"`.

**[I-9] EchoAgent не вызывает Tracker**
- Где: `02_src/core/processing/agents/echo_agent.py`
- Нет TraceEvents `processing_started` / `processing_completed`. Нарушает AC-8.

**[I-10] SIM не записывает TraceEvents `sim_started` / `sim_completed`**
- Где: `02_src/sim/sim.py`

**[I-11] Vite config не подключает React plugin**
- Где: `02_src/vs_ui/vite.config.ts`
- Нет `@vitejs/plugin-react`. JSX/TSX не обработается.

**[I-12] Интеграционный тест ожидает TraceEvents, которые EchoAgent не создаёт**
- Где: `02_src/tests/test_integration.py:61-63`
- Станет зелёным после I-9.

---

## Замечания (желательно исправить) — 9 шт.

| # | Проблема | Где |
|---|----------|-----|
| N-1 | Некорректный отступ (6 вместо 8 пробелов) | `echo_agent.py:84` |
| N-2 | `print()` вместо логгера | `event_bus.py:61`, `echo_agent.py:65,85`, `sim.py:97,113-119` |
| N-3 | `APPLICATION` не читает `DATABASE_URL` из `.env` | `core/api/app.py:23` |
| N-4 | Два `main.py` — неясно какой канонический | `02_src/main.py` vs `02_src/core/main.py` |
| N-5 | `DialogueAgent.start()` не восстанавливает `dialogue_id` из DialogueState | `core/dialogue/agent.py:60-63,92-93` |
| N-6 | `App.tsx` не дедуплицирует events при polling | `vs_ui/src/App.tsx:21` |
| N-7 | `datetime.utcnow()` deprecated в Python 3.12+ | `core/logging_config.py:17` |
| N-8 | `ProcessingLayer` — абсолютные импорты вместо относительных | `core/processing/layer.py:5-8` |
| N-9 | Тест восстановления DialogueState падает (новый UUID вместо сохранённого) | `tests/test_dialogue_agent.py:193` |

---

## Структура папок

Папки `03_data/` и `04_logs/` находятся на **корневом уровне** — корректно.
Проблема только в относительных путях в коде (см. I-2).

---

## .gitignore

**Отсутствует:** `venv/`, `node_modules/`, `__pycache__/`, `*.pyc`, `.env`, `*.db`, `*.log`, `dist/`, `build/`

**Уже закоммичены (должны были быть в .gitignore):**
- `02_src/.env` — реальный API-ключ Anthropic (**КРИТИЧНО**)
- `02_src/vs_ui/.env` — конфигурация

---

## Итого

| Категория | Кол-во |
|-----------|--------|
| Критические (блокируют запуск) | 6 |
| Важные (нужно исправить) | 12 |
| Замечания (желательно) | 9 |

**Главные блокеры:** утечка API-ключа (C-1), сломанные импорты sim (C-2..C-4), ошибка SQL-схемы (C-6), отсутствующий import (C-5). Приложение не запустится без исправления C-2..C-6.

**Рекомендация:** Создать задачу на доработку — исправить все критические + важные, затем перепроверить.
