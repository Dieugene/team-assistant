# Отчет о реализации: Доработка сквозного скелета по результатам ревизии (Review 04)

## Что реализовано

Исправлены критические и важные проблемы из Review 04 и выполнены N‑улучшения: путевая конфигурация, импорты, схема БД, трассировка EchoAgent/SIM, корректные тестовые фикстуры, UI‑фиксы и т.д.

## Файлы

**Новые:**
- `02_src/core/config.py` - централизованные пути и резолв DATABASE_URL
- `02_src/.env.example` - шаблон переменных окружения

**Измененные:**
- `.gitignore` - добавлены правила игнора (env, venv, db, logs, node_modules и др.)
- `02_src/core/app.py` - DB путь из config/env, удалены sim‑импорты, tracker для EchoAgent
- `02_src/core/app_patch.py` - no‑op (SIM инжектится в main.py)
- `02_src/core/api/app.py` - убрано создание SIM, инжект tracker в SIM в lifespan
- `02_src/core/api/routes/control.py` - исправлены пути `/sim/start` и `/sim/stop`
- `02_src/core/logging_config.py` - import logging.config, UTC timestamp, путь логов из config
- `02_src/core/storage/schema.sql` - индексы перенесены после таблиц
- `02_src/core/storage/storage.py` - резолв DB пути, добавлен `get_bus_messages`
- `02_src/core/tracker/tracker.py` - добавлен `stop()`
- `02_src/core/event_bus/event_bus.py` - `print()` заменен на logger
- `02_src/core/processing/agents/echo_agent.py` - tracker, TraceEvents, logger, исправлен отступ
- `02_src/core/processing/layer.py` - относительные импорты
- `02_src/core/dialogue/agent.py` - восстановление `dialogue_id` из DialogueState
- `02_src/sim/sim.py` - tracker инжект, TraceEvents, logger
- `02_src/tests/conftest.py` - исправлены фикстуры DialogueAgent/ProcessingLayer
- `02_src/tests/test_llm_provider.py` - корректный patch path для AsyncAnthropic
- `02_src/vs_ui/vite.config.ts` - добавлен React plugin
- `02_src/vs_ui/src/App.tsx` - дедупликация событий по `event.id`

**Удаленные:**
- `02_src/core/main.py` - единая точка входа только `02_src/main.py`

## Особенности реализации

### Резолв DATABASE_URL и поддержка `:memory:`
**Причина:** нужно обеспечить CWD‑независимость путей и не сломать тесты, использующие `:memory:`.
**Решение:** `core/config.py` возвращает `:memory:` как есть, иначе резолвит относительный путь от PROJECT_ROOT.

## Известные проблемы

- Не удалось установить зависимости в venv: `ensurepip` и `pip install` падают с PermissionError на временных директориях. Из‑за этого не запускались `pytest`, `python main.py` и `npm run dev`. Требуется помощь с разрешениями/окружением, чтобы завершить валидацию AC‑2/AC‑5/AC‑6.
