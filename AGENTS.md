# Okysa Agent Guide

This document provides essential information for agentic coding agents working in the Okysa repository.

## Project Overview
Okysa (formerly NossiBot) is a Discord bot built with `discord.py` and Python 3.14+. It features a dice roller, reminder system, and integration with local tools and services.

## Environment & Commands

### Setup
The project uses `uv` for dependency management.
- **Install dependencies**: `uv sync` or `uv pip install -e .`
- **Python Version**: 3.14 or higher (enforced in `pyproject.toml`).
- **Development dependencies**: `pytest`, `pytest-asyncio`, `pytest-cov`, `pre-commit`.
- **Local gamepack development**: If you need an editable local copy of GamePack (located at `../GamePack`), set `UV_SOURCE_GAMEPACK='{path = "../GamePack", editable = true}'` in your environment or `.env` file. Without this, the git dependency from GitHub is used.

### Build & Lint
- **Formatting**: `black .` (Strict adherence to Black is required)
- **Linting**: `flake8`
- **Pre-commit**: `pre-commit run --all-files` (Runs black, flake8, and various checks)

### Testing
Tests are located in the `tests/` directory and use `pytest`.
- **Run all tests**: `pytest`
- **Run a single test file**: `pytest tests/test_roll.py`
- **Run a specific test**: `pytest tests/test_base.py::test_message_prep`
- **Run with coverage**: `pytest --cov=. --cov-report=text`
- **Async tests**: All async tests should use `@pytest.mark.asyncio`.
- **Filtering warnings**: Pytest is configured to ignore certain DeprecationWarnings in `pyproject.toml`.

## Code Style Guidelines

### Imports
Organize imports into three groups separated by a single blank line:
1. Standard library imports (e.g., `import os`, `import json`)
2. Third-party library imports (e.g., `import discord`, `from aiohttp import ClientSession`)
3. Local application imports (e.g., `from Golconda.Storage import evilsingleton`)

**Order & Loading**:
- Imports ALWAYS come first.
- Loading `dotenv` happens **after** imports in the main entry point (`Okysa.py`).
- Always use absolute imports from the project root. For example, use `from Commands.Base import invoke` instead of `from .Base import invoke`.

### Environment Variables
**NEVER** access environment variables (e.g., `os.getenv`, `os.environ`) at the **module level** (top-level).
- This is mandatory because `load_dotenv()` runs after imports.
- Modules that access environment variables at the top level will fail to see the correct values.
- Access them only within functions or class methods that are called at runtime.

### Formatting
- Use **Black** for all Python files.
- Line length is standard (88 chars as per Black).
- Use double quotes for strings where possible, unless single quotes avoid escaping.
- Indentation is 4 spaces (standard PEP 8).

### Types & Type Hinting
- Provide type hints for all function arguments and return types.
- Example: `def handle_input(data: str) -> bool:`
- Use `|` for unions (Python 3.10+ style): `discord.Client | None`.
- Use `list[]` and `dict[]` instead of `List[]` and `Dict[]` (Python 3.9+ style).

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `RollModal`, `Storage`)
- **Functions & Variables**: `snake_case` (e.g., `evilsingleton()`, `on_message`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_INTENTS`)
- **Modules**: `PascalCase` or `snake_case` (existing modules use `PascalCase` like `Golconda` and `Commands`, but file names are mixed).

### Error Handling
- Use specific exception types. Do not use bare `except:`.
- Define custom exceptions in `Golconda/RollInterface.py` or similar utility modules when needed (e.g., `AuthorError`).
- Use `try...except` blocks in interaction handlers to provide user-friendly error messages via Discord.

## Architecture & Patterns

### Global State & Storage
- **The Evil Singleton**: Access the global state and storage via `Golconda.Storage.evilsingleton()`.
- **Initialization**: Storage is initialized in `Okysa.py` via `Golconda.Storage.setup(client)`.
- **Configuration**: Use `evilsingleton().load_conf(user, key)` and `save_conf` for persistent user/guild settings.
- **Database**: Uses SQLite for persistent storage (e.g., `remind.db`, `chatlogs`).

### Discord Bot Patterns
- **Slash Commands**: Use `discord.app_commands`. Commands are registered in `Commands/__init__.py`.
- **UI Components**: Use `discord.ui.View` and `discord.ui.Modal` for interactive elements.
- **Events**: Main event handlers are in `Okysa.py` (e.g., `on_message`, `on_ready`, `on_raw_message_edit`).
- **Routing**: Message-based commands (prefixed with `?`) are routed via `Golconda.Routing.main_route`.
- **Intents**: `message_content` intent is enabled.

### Module Structure
- `Commands/`: Contains modular command definitions. Each file should have a `register(tree)` function.
- `Golconda/`: Core logic, storage, scheduling, and utility functions.
    - `Storage.py`: Handles persistent data and the `evilsingleton`.
    - `Routing.py`: Handles command routing for non-slash commands.
    - `Scheduling.py`: Handles periodic tasks.
- `Data/`: Static data files used by the bot.

## Testing Patterns

### Fixtures
- Use fixtures defined in `tests/conftest.py`:
    - `mock_user`: A mocked `discord.User`.
    - `mock_channel`: A mocked `discord.TextChannel`.
    - `mock_message`: A mocked `discord.Message`.
    - `mock_interaction`: A mocked `discord.Interaction`.
    - `mock_singleton`: A mocked `Storage` instance.

### Mocking & Async
- Use `unittest.mock.patch` and `AsyncMock` to isolate units of work.
- Example:
  ```python
  @pytest.mark.asyncio
  async def test_feature(mock_message):
      with patch("module.under.test.evilsingleton") as mock_evil:
          await function_to_test(mock_message)
          mock_message.reply.assert_called_once()
  ```

## Development Workflow
1. **Analyze**: Check `Okysa.py` for event flow and `Golconda/` for core logic.
2. **Implement**: Add features or fixes following PEP 8 and Black.
3. **Test**: Write a corresponding test in `tests/` and ensure it passes.
4. **Lint**: Run `black` and `flake8` before submitting changes.
5. **Verify**: Run `pre-commit run --all-files` as a final check.
6. **LSP & Standards**: Ensure all LSP errors are resolved and code follows project standards.
7. **Git Operations**: Only stage relevant files (`git add`). **DO NOT** create commits or push to remote repositories. Commits and pushes are strictly for human contributors.

## Key Dependencies
- `discord-py >= 2.4.0`
- `aiohttp == 3.10.11`
- `uvloop >= 0.21.0` (used for the event loop on Linux)
- `gamepack`: A local dependency (parent directory).

---
*Note: This file is intended for agentic consumption. Be concise, idiomatic, and respect the "evilsingleton" pattern where established.*
