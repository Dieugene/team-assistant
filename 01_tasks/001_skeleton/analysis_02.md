# Технический план: Доработка сквозного скелета по результатам ревизии (Review 04)

## 1. Анализ задачи

Нужно исправить критические и важные проблемы из `01_tasks/001_skeleton/review_04.md`, затем закрыть замечания из блока N-1..N-9 по возможности. Это доработка существующего сквозного скелета: менять архитектуру не требуется, нужно восстановить запуск, корректные импорты, SQL-схему, работу тестов и VS UI. Приоритет работ задан в `01_tasks/001_skeleton/task_brief_02.md` и должен быть сохранен.

Ключевой фокус:
- устранить блокеры запуска и импорта
- привести пути и конфигурацию к независимости от CWD
- восстановить TraceEvents для EchoAgent и SIM
- обеспечить запуск тестов и VS UI

## 2. Текущее состояние

Скелет Iteration 1 реализован и присутствует в `02_src/`, но выявлены проблемы:
- В репозитории есть `.env` с реальным ключом (C-1) и отсутствуют критические записи в `.gitignore`.
- `core/app.py`, `core/app_patch.py`, `core/api/app.py` импортируют `sim` из core и ломают запуск.
- В `core/logging_config.py` отсутствует `import logging.config` и используется `datetime.utcnow()`.
- В `core/storage/schema.sql` индексы создаются до таблиц.
- Пути к `03_data/` и `04_logs/` зашиты относительными строками в нескольких местах.
- В тестах неверные фикстуры, вызываются несуществующие методы `Storage.get_bus_messages()` и `Tracker.stop()`, неверный patch path для LLMProvider.
- В `core/api/routes/control.py` дублируется префикс маршрутов.
- EchoAgent не пишет TraceEvents, SIM не пишет `sim_started` / `sim_completed`.
- В `vs_ui` отсутствует React plugin в Vite config и нет дедупликации событий.
- Есть дублирующий entrypoint `02_src/core/main.py`.

## 3. Предлагаемое решение

### 3.1. Общий подход

Работаем строго по блокам из `task_brief_02.md` и в рекомендованном порядке. Минимизируем правки, не меняем архитектуру: Core не зависит от SIM, SIM остается внешним клиентом, а интеграция делается через `main.py` и control router. Все правки локальны и измеримы критериями AC-1..AC-10.

### 3.2. Компоненты

#### Репозиторий и окружение
Назначение: исключить секреты и мусор из git, дать шаблон переменных окружения.
Файлы:
- `.gitignore` — добавить паттерны из блока 1
- `02_src/.env` — удалить из репозитория
- `02_src/.env.example` — создать шаблон
- `02_src/vs_ui/.env` — убедиться что не коммитится

#### Конфигурация путей
Назначение: абсолютные пути к `03_data/` и `04_logs/` вне зависимости от CWD.
Интерфейс: новый модуль `core/config.py` с константами путей и единым правилом резолва `DATABASE_URL`.
Файлы:
- `02_src/core/config.py` — добавить `PROJECT_ROOT`, `DATA_DIR`, `LOGS_DIR`, `DEFAULT_DB_PATH`, `DEFAULT_LOG_PATH`
- `02_src/core/app.py` — использовать `DEFAULT_DB_PATH`
- `02_src/core/storage/storage.py` — default db_path из config
- `02_src/core/logging_config.py` — default log_file из config

#### Разделение Core и SIM
Назначение: убрать зависимость Core от SIM и привести entrypoint к единому.
Файлы:
- `02_src/core/app.py` — удалить импорт sim
- `02_src/core/app_patch.py` — удалить или оставить пустым, но без sim
- `02_src/core/api/app.py` — убрать создание SIM внутри Core
- `02_src/main.py` — единственный entrypoint, создает SIM и регистрирует в control router
- `02_src/core/main.py` — удалить или заменить на re-export вызова `main()` из `02_src/main.py`

#### SQL-схема
Назначение: схема инициализируется без ошибок.
Файлы:
- `02_src/core/storage/schema.sql` — перенести `CREATE INDEX` после `CREATE TABLE`

#### Логирование
Назначение: исправить импорт и корректный timestamp.
Файлы:
- `02_src/core/logging_config.py` — добавить `import logging.config`, заменить `datetime.utcnow()` на `datetime.now(timezone.utc)`

#### Тесты и контракты
Назначение: тесты запускаются без ImportError/AttributeError.
Файлы:
- `02_src/tests/conftest.py` — исправить порядок аргументов для `DialogueAgent`, сигнатуру `ProcessingLayer`
- `02_src/core/storage/storage.py` — добавить `get_bus_messages()`
- `02_src/core/tracker.py` — добавить `stop()` (может быть no-op)
- `02_src/tests/test_event_bus.py` — использовать новый метод хранения
- `02_src/tests/test_tracker.py` — использовать новый `stop()`
- `02_src/tests/test_llm_provider.py` — корректный patch path и async mock

#### Control API
Назначение: корректные пути управления SIM.
Файлы:
- `02_src/core/api/routes/control.py` — заменить `"/api/control/sim/start"` и `"/api/control/sim/stop"` на `"/sim/start"` и `"/sim/stop"`

#### EchoAgent TraceEvents
Назначение: писать `processing_started` и `processing_completed`.
Файлы:
- `02_src/core/processing/agents/echo_agent.py` — добавить зависимость `tracker`, заменить `print()` на `tracker.track()`
- `02_src/core/app.py` — передать tracker в EchoAgent

#### SIM TraceEvents
Назначение: писать `sim_started` / `sim_completed`.
Подход: вариант B из task_brief, без изменения API.
Файлы:
- `02_src/sim/sim.py` — добавить возможность получать `tracker` и вызывать `track()` при старте/завершении
- `02_src/core/api/app.py` — в `lifespan` после `application.start()` установить tracker в SIM, если SIM зарегистрирован в control router
- `02_src/core/api/routes/control.py` — использовать `get_sim_instance()` как источник SIM

#### VS UI
Назначение: запуск Vite и корректная работа Timeline.
Файлы:
- `02_src/vs_ui/vite.config.ts` — подключить `@vitejs/plugin-react`
- `02_src/vs_ui/src/App.tsx` — дедупликация событий по `event.id`

#### Прочие замечания (N-блок)
Назначение: снизить техдолг без влияния на архитектуру.
Файлы:
- `02_src/core/event_bus.py`, `02_src/core/processing/agents/echo_agent.py`, `02_src/sim/sim.py` — заменить `print()` на logger
- `02_src/core/processing/layer.py` — относительные импорты
- `02_src/core/dialogue/agent.py` — восстанавливать `dialogue_id` из `DialogueState` при `start()`

### 3.3. Структуры данных

Новых моделей данных не добавляется. Вводятся только константы путей в `core/config.py`:
- `PROJECT_ROOT`
- `DATA_DIR`
- `LOGS_DIR`
- `DEFAULT_DB_PATH`
- `DEFAULT_LOG_PATH`

### 3.4. Ключевые алгоритмы

- SIM должен вызывать `tracker.track()` при старте и завершении сценария с данными `scenario`, `user_count`, `message_count`.
- EchoAgent должен писать TraceEvents на входе и выходе обработки, используя `actor = f"agent:{agent_id}"`.
- `DialogueAgent.start()` должен восстанавливать `dialogue_id` из `DialogueState`, если он существует в Storage.

### 3.5. Изменения в существующем коде

Обязательные изменения затрагивают:
- `02_src/core/app.py`
- `02_src/core/app_patch.py`
- `02_src/core/api/app.py`
- `02_src/core/api/routes/control.py`
- `02_src/core/logging_config.py`
- `02_src/core/storage/schema.sql`
- `02_src/core/storage/storage.py`
- `02_src/core/processing/agents/echo_agent.py`
- `02_src/core/processing/layer.py`
- `02_src/core/dialogue/agent.py`
- `02_src/sim/sim.py`
- `02_src/vs_ui/vite.config.ts`
- `02_src/vs_ui/src/App.tsx`
- `02_src/tests/conftest.py`
- `02_src/tests/test_event_bus.py`
- `02_src/tests/test_tracker.py`
- `02_src/tests/test_llm_provider.py`
- `.gitignore`
- `02_src/.env.example`

## 4. План реализации

1. Обновить `.gitignore` и создать `02_src/.env.example`, удалить коммит `.env`.
2. Создать `core/config.py` и перевести пути к данным и логам на абсолютные.
3. Исправить SQL-схему (перенос индексов).
4. Добавить `import logging.config` и обновить timestamp в `logging_config.py`.
5. Убрать sim-импорты из Core, оставить SIM только в `main.py`, привести к одному entrypoint.
6. Исправить EchoAgent и Tracker TraceEvents.
7. Исправить маршруты Control API.
8. Исправить фикстуры тестов и добавить отсутствующие методы в Storage и Tracker.
9. Исправить тесты LLMProvider (patch path, async mocks).
10. Исправить SIM TraceEvents (вариант B).
11. Исправить Vite config и дедупликацию событий в VS UI.
12. Закрыть N-блок (print -> logger, imports, DialogueState restore).
13. Прогнать `pytest`, `python -m core.app` или `python main.py`, и `npm run dev` в `02_src/vs_ui/`.

## 5. Технические критерии приемки

Обязательные:
- [ ] AC-1: `.gitignore` настроен согласно блоку 1
- [ ] AC-2: Приложение запускается без ошибок (`python -m core.app` или `python main.py`)
- [ ] AC-3: Нет ImportError, все импорты корректны
- [ ] AC-4: SQL-схема инициализируется без ошибок
- [ ] AC-5: `pytest` запускается без SyntaxError/ImportError
- [ ] AC-6: VS UI запускается (`npm run dev` в `02_src/vs_ui/`)
- [ ] AC-7: Пути к `03_data/` и `04_logs/` работают независимо от CWD
- [ ] AC-8: EchoAgent пишет TraceEvents `processing_started` и `processing_completed`
- [ ] AC-9: Единственная точка входа — `02_src/main.py`
- [ ] AC-10: Создан `02_src/.env.example` без реальных значений

Желательные (N-блок):
- [ ] N-1: Исправлен отступ в `echo_agent.py`
- [ ] N-2: `print()` заменены на logger в core и SIM
- [ ] N-3: `DATABASE_URL` читается из окружения
- [ ] N-4: Удален или переэкспортирован `02_src/core/main.py`
- [ ] N-5: `DialogueAgent.start()` восстанавливает `dialogue_id`
- [ ] N-6: `App.tsx` дедуплицирует события по `event.id`
- [ ] N-7: `datetime.utcnow()` заменен на `datetime.now(timezone.utc)`
- [ ] N-8: `ProcessingLayer` использует относительные импорты
- [ ] N-9: Тест `test_start_restores_dialogue_state` проходит

## 6. Важные детали для Developer

- C-1 требует немедленной ротации ключа Anthropic и очистки ключа из истории git. Это процессный шаг, согласовать с Tech Lead.
- После правок схемы и путей желательно удалить локальный файл БД в `03_data/` для чистой инициализации.
- Резолв `DATABASE_URL`: если путь относительный, строить от `PROJECT_ROOT`, если абсолютный — использовать как есть.
- Для `LOGS_DIR` и `DATA_DIR` нужно обеспечить `mkdir(parents=True, exist_ok=True)` до использования.
- В TraceEvents EchoAgent и SIM использовать event_type из implementation plan: `processing_started`, `processing_completed`, `sim_started`, `sim_completed`.
- В `DialogueAgent.start()` нужно загружать `DialogueState` и восстанавливать `dialogue_id`, иначе падает тест N-9.
- В VS UI дедупликацию выполнять по `event.id` с сохранением сортировки по времени.
