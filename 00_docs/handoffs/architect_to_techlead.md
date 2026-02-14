# Передача: Architect → Tech Lead

**Дата:** 2026-02-14

## Что сделано

Архитектурная документация завершена и готова к реализации.

## Документы архитектуры (в порядке чтения)

1. `00_docs/architecture/glossary.md` — единый язык проекта
2. `00_docs/architecture/concept.md` — видение, подход, границы MVP
3. `00_docs/architecture/core/components.md` — структура Core (7 компонентов)
4. `00_docs/architecture/core/scenarios.md` — сценарии работы компонентов
5. `00_docs/architecture/core/data_model.md` — сущности, связи, инварианты
6. `00_docs/architecture/interfaces.md` — интерфейсы на границе Core
7. `00_docs/architecture/visualization/overview.md` — VS UI
8. `00_docs/architecture/dev_slices.md` — принцип нарезки на блоки разработки

## Задача

Построить план имплементации на основе архитектуры.
Критично: прочитать `dev_slices.md` — там зафиксирован принцип
вертикальных срезов и описание первого блока (сквозной скелет).

## Ключевые решения (для справки)

- BusMessage и TraceEvent — разные сущности (не путать)
- BusMessages персистентны через EventBus → Storage (возможен TTL)
- TraceEvents — единственный источник данных для VS UI
- DialogueBuffer — вычисляемый подмассив Messages, не отдельная сущность
- Core — long-running process (не serverless)
- Storage — SQLite для MVP
