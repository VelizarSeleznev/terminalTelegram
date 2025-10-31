from __future__ import annotations

from datetime import datetime
from typing import Optional

from .io import IOInterface
from .models import DialogData, MessageData
from .service import TelegramServiceProtocol


class TerminalController:
    """Event loop driving the terminal chat experience."""

    PROMPT = "msg (:help for commands)> "

    def __init__(
        self,
        service: TelegramServiceProtocol,
        io: IOInterface,
        message_fetch_limit: int = 25,
    ) -> None:
        self._service = service
        self._io = io
        self._message_fetch_limit = message_fetch_limit
        self._dialogs: list[DialogData] = []
        self._current_dialog_index: Optional[int] = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._service.connect()
        self._io.write("Connected to Telegram.")
        await self._refresh_dialogs()
        if self._dialogs:
            await self._open_dialog(0)
        else:
            self._io.write("No dialogs found. Start a conversation from another client.")
        self._io.write("Type messages to send them. Commands start with ':'. Type :help for guidance.")

        while self._running:
            try:
                user_input = self._io.read(self.PROMPT)
            except EOFError:
                break
            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.startswith(":"):
                await self._handle_command(user_input[1:])
            else:
                await self._send_message(user_input)

        await self._service.disconnect()
        self._io.write("Disconnected.")

    async def _refresh_dialogs(self) -> None:
        self._dialogs = await self._service.fetch_dialogs()
        self._display_dialog_list()

    async def _open_dialog(self, index: int) -> None:
        if index < 0 or index >= len(self._dialogs):
            self._io.write(f"Invalid dialog index: {index}")
            return
        self._current_dialog_index = index
        dialog = self._dialogs[index]
        header = f"--- {dialog.title} ---"
        self._io.write(header)
        await self._display_messages(dialog)

    async def _display_messages(self, dialog: DialogData) -> None:
        messages = await self._service.fetch_messages(dialog, limit=self._message_fetch_limit)
        if not messages:
            self._io.write("No messages yet.")
            return
        for message in messages:
            self._io.write(self._format_message(message))

    async def _handle_command(self, command: str) -> None:
        normalized = command.strip()
        if not normalized:
            return
        if normalized in {"q", "quit", "exit"}:
            self._running = False
            return
        if normalized in {"h", "help"}:
            self._show_help()
            return
        if normalized in {"d", "dialogs"}:
            self._display_dialog_list()
            return
        if normalized in {"r", "reload"}:
            await self._refresh_dialogs()
            return
        if normalized in {"m", "more"}:
            await self._load_more_messages()
            return
        if normalized.startswith("open"):
            parts = normalized.split()
            if len(parts) == 2 and parts[1].isdigit():
                await self._open_dialog(int(parts[1]))
                return
        if normalized.isdigit():
            await self._open_dialog(int(normalized))
            return
        self._io.write(f"Unknown command: :{command}")

    async def _send_message(self, text: str) -> None:
        dialog = self._current_dialog()
        if dialog is None:
            self._io.write("Choose a dialog before sending messages (:dialogs).")
            return
        await self._service.send_message(dialog, text)
        await self._display_messages(dialog)

    async def _load_more_messages(self) -> None:
        self._message_fetch_limit += 25
        dialog = self._current_dialog()
        if dialog is None:
            self._io.write("No active dialog to load more messages from.")
            return
        await self._display_messages(dialog)

    def _display_dialog_list(self) -> None:
        if not self._dialogs:
            self._io.write("No dialogs available.")
            return
        self._io.write("Dialogs:")
        for idx, dialog in enumerate(self._dialogs):
            marker = "*" if idx == self._current_dialog_index else " "
            self._io.write(f" {marker} {idx}: {dialog.title}")

    def _show_help(self) -> None:
        self._io.write(
            "Commands:\n"
            "  :<number>        Switch to dialog by index\n"
            "  :open <number>   Same as :<number>\n"
            "  :dialogs         Show dialog list\n"
            "  :more            Load more history\n"
            "  :reload          Reload dialogs\n"
            "  :help            Show this help\n"
            "  :quit            Exit the client"
        )

    def _current_dialog(self) -> Optional[DialogData]:
        if self._current_dialog_index is None:
            return None
        if 0 <= self._current_dialog_index < len(self._dialogs):
            return self._dialogs[self._current_dialog_index]
        return None

    def _format_message(self, message: MessageData) -> str:
        direction = "->" if message.is_outgoing else "<-"
        timestamp = self._format_timestamp(message.timestamp)
        text = message.text if message.text else ("<media>" if message.has_media else "<empty>")
        return f"{direction} [{timestamp}] {message.sender}: {text}"

    @staticmethod
    def _format_timestamp(timestamp: datetime) -> str:
        return timestamp.strftime("%Y-%m-%d %H:%M")
