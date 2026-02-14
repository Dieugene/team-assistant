# Передача дел: Architect

**Дата:** 2026-02-14

## Что сделано
- Архивированы старые доки в `00_docs/architecture/_archive/`
- Создан `glossary.md` — концептуальная модель, 8 смысловых разделов, ~20 терминов
- Создан `concept.md` — проблема, подход, принципы, стратегия, границы MVP
- Создан `core/components.md` — архитектурный скелет Core (7 верхнеуровневых компонентов)
- Создан `core/scenarios.md` — 3 сценария (основной поток, жизненный цикл, SIM)
- Создан `visualization/overview.md` — VS UI: назначение, представления, связь с Core

## Текущий статус
Архитектурный каркас документации сформирован; visualization/overview.md требует правок перед продолжением.

## Ключевые решения
- **"Event" разделён на два понятия:** BusMessage (межкомпонентная коммуникация) и TraceEvent (наблюдаемость) — это разные сущности
- **Topics шины:** input / processed / output (вместо raw / processed / notification) — обобщение для будущего расширения
- **TraceEvents — единственный источник для VS UI:** вариант A — Tracker вкладывает полные данные, VS UI не обращается к Messages/AgentState напрямую
- **OutputRouter — верхнеуровневый компонент**, стоит между EventBus(output) и DialogueAgent
- **ContextAgent убран с архитектурного уровня** — появится в детальных спецификациях
- **SIM двухуровневый:** Profile (индивидуальный, из реальных чатов) + Scenario (командный поток событий)
- **Core — long-running process** (не serverless)

## Что важно знать преемнику
- **НЕМЕДЛЕННАЯ ПРАВКА:** в `visualization/overview.md` раздел 3 "Типизация TraceEvents" — таблица с примерами типов слишком детальна для архитектурного уровня и содержит ошибку: message_received/responded НЕ должны быть в Timeline. В Timeline — события из EventBus (публикация фрагмента диалога), а не отдельные сообщения. Нужно либо убрать таблицу, либо переработать до уровня принципа без конкретных типов.
- Документация строится через диалог с заказчиком — не переписывать из архивных доков, а проговаривать каждое решение
- Глоссарий — императивный документ: все термины в архитектуре ОБЯЗАНЫ быть из глоссария. Заказчик хочет роль Glossary Agent для управления терминологией.
- Архивные доки (`_archive/`) — сырой материал, не целевой результат

## Следующие шаги
1. Исправить раздел 3 в `visualization/overview.md` (см. выше)
2. Создать `core/data_model.md` — сущности хранения (Messages, DialogueState, AgentState, TraceEvents)
3. Создать `core/event_bus.md` — формат BusMessage, Topics, паттерны подписки
4. Создать `simulation/sim.md` — SIM-модуль: Profile, Scenario, конфигурация через файлы
5. Согласовать с заказчиком оставшиеся документы (visualization/ детали, decisions/)

## Файлы для чтения
- `00_docs/architecture/glossary.md` — фундамент, единый язык
- `00_docs/architecture/concept.md` — видение и границы MVP
- `00_docs/architecture/core/components.md` — архитектурный скелет
- `00_docs/architecture/core/scenarios.md` — как компоненты работают вместе
- `00_docs/architecture/visualization/overview.md` — VS UI (ТРЕБУЕТ ПРАВОК, см. выше)
