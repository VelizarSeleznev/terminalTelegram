Terminal Telegram Client (Telethon)
===================================

This project provides a keyboard-driven terminal interface for Telegram built on top of [Telethon](https://docs.telethon.dev/) and [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit). The default UI gives you an arrow-key dialog picker, live conversation view, and a message box that is always one keypress away.

Features
--------
- Automatic login flow (phone, code, and 2FA password prompts).
- Interactive split-view UI: left column for dialogs, right for messages, bottom line for composing.
- Intuitive shortcuts (arrows to navigate, `Enter` to compose, `Esc` to jump back, `PgUp` for history, `Ctrl+R` to reload, `Ctrl+C` to quit).
- Optional legacy mode that keeps the original colon-command prompt for scripting or minimal shells.

Getting Started
---------------
1. **Install dependencies**

   ```bash
   pip install -e .
   ```

   Optionally install the dev extras for running tests:

   ```bash
   pip install -e .[dev]
   ```

2. **Run the client**

   ```bash
   python -m termainaltelegram
   ```

   Environment variables `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_SESSION` are respected. Defaults are set to the API credentials provided in the task, so you can start immediately if they are acceptable.

   Prefer `uv run python -m termainaltelegram` if you are using Astral's uv manager.

Usage Cheatsheet (Interactive UI)
---------------------------------
- `↑` / `↓` — move through dialogs (focus starts on the dialog list).
- `→` — move focus to the message viewer; `←` returns to the dialog list.
- `Enter` or `Tab` — jump into the compose box and start typing; `Esc` backs out.
- `Ctrl+Y` — load 25 more historical messages for the active chat.
- `Ctrl+R` — refresh the dialog list.
- `Ctrl+C` or `Ctrl+Q` — exit the application.
- Messages send on `Enter`; the input clears automatically after dispatch.

Legacy Prompt Mode
------------------
If you prefer the colon-command interface (or need a simpler REPL for automation), pass `--mode legacy`:

```bash
python -m termainaltelegram --mode legacy
```

Testing
-------
Run the automated tests with:

```bash
pytest
```

The test suite stubs Telegram interactions, so it runs without live network access.
