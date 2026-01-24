# Передача дел: Architect

**Дата:** 2025-01-24
**Сессия:** team-assistant-architect

## Что сделано
- Создана `00_docs/architecture/overview.md` — детальная архитектура системы
- Создана `00_docs/architecture/visualization.md` — требования к визуализации
- Обновлен `README.md` — актуальное описание проекта
- Проведено обсуждение архитектуры с пользователем, учтены все корректировки
- **Проведена ревизия и исправлены логические противоречия** (см. ниже)

## Текущий статус

Архитектура обновлена после ревизии. Исправлены следующие проблемы:

### Исправленные противоречия:

1. **DialogueAgent детекция таймаута** — добавлен фоновый процесс `timeout_checker` для проверки неактивных диалогов

2. **IStorage vs Репозитории** — IStorage сделан универсальным (generic CRUD), бизнес-логика вынесена в типизированные репозитории:
   - `MessageRepository`
   - `TaskRepository`
   - `AgentStateRepository`
   - `AgentConversationRepository`
   - `UserContextRepository`
   - `NotificationLogRepository`

3. **Reasoning format** — изменен с `Optional[str]` на `Optional[ReasoningTrace]` (структура с полями)

4. **SIM интеграция** — исправлено, SIM работает только через `DialogueAgent.on_message()`, не генерирует события напрямую

5. **State vs Memory** — добавлен раздел с пояснением разницы между state, memory и in-memory cache

6. **Dialogue Boundary vs Tracking** — пояснена разница между Event Bus (коммуникация) и Tracking (VS UI)

7. **Reasoning traces** — добавлен пример где вызывается `events.track()` внутри `process()`

### Детализация DialogueAgent:

Расписана архитектура DialogueAgent с:
- Тремя точками активации: `on_message()`, `check_timeouts()`, `on_bus_event()`
- Состоянием диалога (`DialogueState`)
- Диалоговой политикой (`DialoguePolicy`)
- Фоновым процессом для таймаутов

## Ключевые решения

1. **Единая диалоговая система** — Dialogue & Notify Agents используют общую диалоговую политику, не разделены
2. **Processing Agents сами решают** — агенты помечают recipients в `ProcessingResult.notifications`, нет check relevance в Notify Agent
3. **Уровни абстракции** — Event Bus (транспорт) и Storage (инфраструктура) разделены
4. **Интерфейс для агентов** — `IProcessingAgent` как точка расширения, Tech Lead НЕ занимается составом агентов
5. **Система агентов позже** — сначала рамочная система, потом отдельная ветка разработки агентов
6. **Примеры агентов** — TaskManager (ведет базу задач) и ContextManager (движение информации), НЕ TaskExtractor/DeadlineTracker
7. **Наглядность > Real-time** — задержка 1+ секунда норма, polling достаточен
8. **Timeline графический** — НЕ текстовый список, позиция на оси = момент времени

## Что важно знать преемнику

**Критичные детали из обсуждения:**
- Пользователь правильно указал на "перекос" в Dialogue Agent — был акцент на завершении диалога, исправлено на фокус на диалоговой системе
- Notify Agent не делает check relevance — это сложная агентная логика, агенты сами помечают что кому
- Event Bus и Storage — разные уровни абстракции (транспорт vs инфраструктура), пользователь это подчеркнул
- Tech Lead не будет заниматься составом Processing Agents — будет интерфейс, потом отдельная ветка
- SGR Agent Core выбран как база для processing agents, но это детализация, архитектурно — "подключаемые агенты"
- SQLite для dev, YDB для prod — пользователь подчеркнул что это не для продакшена сейчас
- Storage conversations — SGR хранит в памяти, мы сохраняем в Storage для персистентности

**После ревизии:**
- IStorage универсальный, бизнес-логика в репозиториях
- DialogueAgent имеет три точки активации (message, timeout, bus event)
- Разница между Event Bus (коммуникация) и Tracking (VS UI) явно прописана
- SIM только через DialogueAgent, не генерирует события напрямую

**Пожелания пользователя:**
- Визуализация — отдельный файл `visualization.md` создан
- Все пожелания из обсуждения там зафиксированы
- Отдельный архитектор для VS может потребоваться

**Философия проекта:**
- MVP-first: простейшая работающая система
- Observability-first: все действия должны быть видимы в VS UI
- Порты и адаптеры: интерфейсы для замены реализаций

## Следующие шаги

1. → **Tech Lead:** Создать `implementation_plan.md`, `backlog.md`, task briefs
2. → **ADR:** Выбор БД для продакшена (когда станет актуально)
3. → **Architect VS:** Детальная архитектура визуализации (если потребуется)

## Файлы для чтения

- `00_docs/architecture/overview.md` — основная архитектура (обязательно, обновлена)
- `00_docs/architecture/visualization.md` — требования к VS UI (обязательно)
- `README.md` — общее описание проекта (для контекста)
- `.agents/architect.md` — роль архитектора (для понимания задач)

---

**Для запуска Tech Lead используй промпт ниже:**

```
Ты — Tech Lead (см. .agents/tech-lead.md).

Прочитай:
- .agents/tech-lead.md
- AGENTS.md
- 00_docs/standards/common/*
- 00_docs/standards/tech-lead/*
- 00_docs/architecture/overview.md
- Все ADR из 00_docs/architecture/decision_*.md

Задача: Создай implementation plan, backlog и первые задачи для команды.

Определи порядок реализации модулей, спроектируй интерфейсы, разбей на итерации.

Учти:
- IStorage универсальный, бизнес-логика в репозиториях
- DialogueAgent имеет три точки активации
- ProcessingResult.reasoning имеет тип ReasoningTrace (структура, не строка)
```
