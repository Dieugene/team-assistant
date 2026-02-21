# Skeleton Fixes Design

**Date:** 2026-02-14

## Goal
Restore a runnable skeleton by fixing critical and important issues from Review 04, plus N-block improvements where safe, without changing architecture (Core does not depend on SIM).

## Scope
- Repo hygiene: `.gitignore`, `.env.example`
- Absolute paths via `core/config.py` (CWD-independent)
- SQL schema ordering
- Logging import and UTC timestamp
- Remove SIM imports from Core; SIM created only in `02_src/main.py`
- TraceEvents for EchoAgent and SIM (via Tracker)
- Control API route prefix fix
- Test fixture and mock corrections
- VS UI: React plugin + event dedup
- Minor N-block fixes: print -> logger, relative imports, restore dialogue_id

## Non-Goals
- Architectural refactors
- New product features
- Test expansion beyond required fixes

## Design Overview
- Add `core/config.py` to centralize project root and default paths. Resolve `DATABASE_URL` relative to project root if needed, ensure `03_data/` and `04_logs/` exist.
- Core classes use config defaults (`Application`, `Storage`, `setup_logging`).
- `core/*` no longer imports SIM; SIM is instantiated in `main.py` and registered in control router.
- `lifespan` injects Tracker into SIM if present. SIM uses Tracker to emit `sim_started`/`sim_completed`.
- EchoAgent adds Tracker dependency and emits `processing_started`/`processing_completed`.

## Testing Strategy
- Run existing `pytest` suite (no new tests unless required).
- Smoke: `python main.py` for Core app boot and schema init.
- UI: `npm run dev` from `02_src/vs_ui`.

## Risks
- Changing defaults for DB/log paths could affect local setups; mitigate by honoring absolute `DATABASE_URL`.
- Tracker injection into SIM requires a safe optional API (no hard dependency).
