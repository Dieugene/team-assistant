# Iteration 2: Содержательная обработка — TaskExtractor ProcessingAgent

## Что нужно сделать

Заменить текущий `echo_agent` на содержательный `TaskExtractorAgent`, который извлекает задачи из входных фрагментов диалога и публикует структурированный результат в `output`.

Реализация должна встроиться в текущий сквозной pipeline (`SIM -> Core -> VS UI`) без поломки существующей наблюдаемости.

## Зачем

После завершения скелета (001) система должна перейти от технической проверки потока данных к полезной обработке контента. Цель Iteration 2 — получить первые практически полезные результаты из диалогов и подготовить данные/трейсы для Iteration 3 (Agent Reasoning в UI).

## Acceptance Criteria

- [ ] AC-1: Вместо `echo_agent` в `ProcessingLayer` используется `TaskExtractorAgent` (или эквивалентный агент с тем же назначением).
- [ ] AC-2: Агент подписывается на `topic=input`, обрабатывает payload, публикует результат в `topic=output`.
- [ ] AC-3: Результат обработки содержит структурированные задачи (минимум: `title`, `assignee|owner`, `priority|urgency`, `due_date|time_hint`, `source_dialogue_id`).
- [ ] AC-4: `AgentState` используется для сохранения контекста между обработками и реально обновляется.
- [ ] AC-5: `Tracker` фиксирует как минимум `processing_started` и `processing_completed` для агента.
- [ ] AC-6: В `VS UI Timeline` видны события обработки и публикации результата с понятным содержимым.
- [ ] AC-7: `pytest` запускается без `SyntaxError/ImportError` (не обязательно полностью green, но без падения из-за базовых ошибок импорта/синтаксиса).
- [ ] AC-8: E2E smoke: после `Start SIM` в Timeline появляются события с результатами TaskExtractor, а не `Echo: ...`.

## Контекст

### Релевантные части implementation plan (Iteration 2)

- Цель Iteration 2: заменить `echo`-обработку на осмысленную.
- Основной модуль: `TaskExtractor ProcessingAgent`.
- Результаты обработки должны быть видимы в VS UI.
- `AgentState` должен хранить контекст между обработками.
- Нужны SGR/Reasoning traces как подготовка к Iteration 3.

### Интерфейсы и контракты (базовые)

```python
class IProcessingAgent(Protocol):
    @property
    def agent_id(self) -> str: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

```python
class IProcessingLayer(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def register_agent(self, agent: IProcessingAgent) -> None: ...
```

```python
class ITracker(Protocol):
    async def track(self, event_type: str, actor: str, data: dict) -> None: ...
```

```python
class IStorage(Protocol):
    async def save_agent_state(self, agent_id: str, state: AgentState) -> None: ...
    async def get_agent_state(self, agent_id: str) -> AgentState | None: ...
```

```python
class TaskExtractorAgent(IProcessingAgent):
    agent_id = "task_extractor"
    async def handle_input(self, bus_message: BusMessage) -> None:
        # 1) get AgentState
        # 2) LLM extraction
        # 3) update AgentState
        # 4) publish output
        # 5) track events
        ...
```

### Ограничения и решения

- Использовать текущую архитектуру Core без архитектурных изменений.
- Не удалять существующую наблюдаемость, а расширить ее данными TaskExtractor.
- Для Iteration 2 допускается реальный `LLMProvider` (Anthropic), ключ берется из `.env`.
- Формат output должен быть пригоден для отображения в Timeline и последующей детализации в Iteration 3.

### Критерии готовности модуля

- Агент стабильно проходит lifecycle `start/stop`.
- Публикация `output` не ломает текущий OutputRouter.
- TraceEvents информативны и содержат достаточные данные для анализа причинно-следственной цепочки.
- E2E smoke воспроизводим локально через `python 02_src/main.py` + `npm run dev`.

