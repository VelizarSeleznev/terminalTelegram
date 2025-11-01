# Repository Guidelines

## Project Structure & Module Organization
- `termainaltelegram/` holds the runtime code: `cli.py` wires the prompt, `controller.py` orchestrates chat flow, `service.py` wraps Telethon, and `ui.py` defines prompt-toolkit layouts.
- `tests/` mirrors core modules with async-friendly pytest suites; add new fixtures in `tests/conftest.py`.
- `main.py` provides a minimal entry point for manual runs; package metadata lives in `pyproject.toml`.

## Build, Test, and Development Commands
- Install in editable mode with dev extras: `pip install -e .[dev]`.
- Launch the client from the package: `python -m termainaltelegram` (or `uv run python -m termainaltelegram` when using Astral uv).
- Run all tests: `pytest`. Use `pytest tests/test_ui.py -k dialog` when iterating on a single flow.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation; keep line length under 100 characters to match existing modules.
- Preserve type hints (`from __future__ import annotations`) and prefer descriptive dataclass-style names like `DialogData`.
- Organize imports into standard library, third-party, then local modules. Use lowercase module filenames; new async helpers should live beside related logic in `service.py` or `controller.py`.

## Testing Guidelines
- Tests use pytest with `pytest-asyncio`; mark async coroutines with `@pytest.mark.asyncio`.
- Place new suites under `tests/` using `test_<module>.py` naming. Mock Telethon interactions via the existing fixtures before hitting the network.
- Maintain behavioural parity by covering message fetch/send paths and UI state transitions whenever you extend controllers or services.

## Commit & Pull Request Guidelines
- Keep commits small, with imperative subjects (`Add dialog pagination`). Reference issues using `Refs #123` in the body when applicable.
- For pull requests, include a brief summary, testing notes (`pytest` results), and screenshots or terminal captures when the UI changes.
- Ensure CI passes locally (`pytest`) before requesting review; flag any known limitations in the PR description.

## Configuration & Security Tips
- Required environment variables: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and optional `TELEGRAM_SESSION` path for persistent logins.
- Do not commit session files or API credentials; add ad-hoc secrets to your shell environment during development instead.
