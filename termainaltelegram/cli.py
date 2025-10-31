from __future__ import annotations

import argparse
import asyncio
import os
from typing import Optional

from .controller import TerminalController
from .io import StdIO
from .service import TelethonService
from .ui import PromptToolkitChatUI

DEFAULT_API_ID = 24144743
DEFAULT_API_HASH = "99905ea6025c351db01950d56a499ce0"


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Terminal interface for Telegram (Telethon-based).")
    parser.add_argument("--api-id", type=int, default=_env_int("TELEGRAM_API_ID", DEFAULT_API_ID))
    parser.add_argument("--api-hash", default=os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH))
    parser.add_argument("--session", default=os.getenv("TELEGRAM_SESSION", "terminal_session"))
    parser.add_argument("--limit", type=int, default=25, help="Initial number of messages to load.")
    parser.add_argument(
        "--mode",
        choices=("interactive", "legacy"),
        default=os.getenv("TERMINAL_TELEGRAM_MODE", "interactive"),
        help="`interactive` launches the prompt_toolkit UI, `legacy` keeps the simple prompt.",
    )
    args = parser.parse_args(argv)

    io = StdIO()
    service = TelethonService(
        api_id=args.api_id,
        api_hash=args.api_hash,
        session_name=args.session,
        io=io,
    )

    try:
        if args.mode == "legacy":
            controller = TerminalController(service=service, io=io, message_fetch_limit=args.limit)
            asyncio.run(controller.start())
        else:
            ui = PromptToolkitChatUI(service=service, message_fetch_limit=args.limit)
            asyncio.run(ui.run())
    except KeyboardInterrupt:
        io.write("\nInterrupted, shutting down...")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
