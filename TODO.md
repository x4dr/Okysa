# Okysa Project Improvements TODO

## Phase 1: Type Safety & Code Consistency (Option 1)
- [x] **Add missing type hints**
    - [x] `Okysa.py` event handlers and functions.
    - [x] `Golconda/RollInterface.py` basic types.
    - [x] `Golconda/Tools.py` types and return hints.
    - [x] `Golconda/CharacterService.py` (New module with full types).
    - [ ] `Commands/` modules (partially done).
- [x] **Rename modules for consistency**
    - [x] Rename `Golconda/eastereggs.py` to `Golconda/EasterEggs.py`.
- [x] **Standardize constants**
    - [x] Convert `numemoji` and `numemoji_2` in `RollInterface.py` to `NUM_EMOJI` and `NUM_EMOJI_2`.
- [x] **Enforce PascalCase for all module files**

## Phase 2: Architectural Security & Stability (Option 2)
- [x] **Safe Dice Rolling**
    - [x] Remove unused unsafe `terminate_thread`.
    - [x] Implement robust `timeout` using `multiprocessing.Pool` and `run_in_executor`.
- [x] **Environment Configuration**
    - [x] Replace hardcoded `~/wiki` in `Golconda/Clocks.py` with the `WIKI` environment variable.

## Phase 3: Refactoring & Logic Consolidation (Modified Option 3)
- [x] **Centralize Character Logic**
    - [x] Create `Golconda/CharacterService.py`.
    - [x] Move logic from `Commands/Base.py`, `Commands/Char.py`, and `Golconda/Tools.py`.
- [ ] **Refine Error Handling**
    - [x] Audit `except Exception:` in `Storage.py`.
    - [ ] Audit remaining `except Exception:` blocks.
    - [ ] Ensure slash commands provide ephemeral feedback on errors.

## Phase 4: Testing & Coverage (Modified Option 4)
- [x] **Increase Test Coverage**
    - [x] Add unit tests for `Golconda/Reminder.py` (TZ handling, new reminders).
    - [x] Add basic unit tests for `Golconda/Routing.py`.


## Phase 4: Testing & Coverage (Modified Option 4)
- [ ] **Increase Test Coverage**
    - [ ] Add unit tests for `Golconda/Reminder.py`.
    - [ ] Add unit tests for `Golconda/Routing.py`.
    - [ ] Ensure async tests use `@pytest.mark.asyncio`.

---
## Implementation Notes & Hints

### Safe Dice Rolling (Multiprocessing)
The current implementation force-terminates threads, which is unsafe. Use `multiprocessing.Process` with a `Queue` or `Pipe` to run `Dice.roll()` and capture results. Use `process.join(timeout=...)` and `process.terminate()` if it exceeds the limit.

### Character Logic Centralization
Look for `get_discord_user_char` and similar patterns. Create a `Golconda/CharacterService.py` or similar to handle mapping Discord IDs to character data.

### Specific Exceptions
Check `Golconda/RollInterface.py` for `AuthorError`. We should probably have `ConfigError`, `DatabaseError`, and `DiscordAPIError` as well.
