from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, VSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.document import Document

from .models import DialogData, MessageData
from .service import TelegramServiceProtocol


@dataclass(slots=True)
class _UIState:
    dialogs: List[DialogData]
    messages: List[MessageData]
    current_dialog_index: Optional[int]
    status_message: str


class PromptToolkitChatUI:
    """prompt_toolkit-based interface with dialog picker and message viewer."""

    def __init__(
        self,
        service: TelegramServiceProtocol,
        message_fetch_limit: int = 25,
    ) -> None:
        self._service = service
        self._message_fetch_limit = message_fetch_limit
        self._state = _UIState(dialogs=[], messages=[], current_dialog_index=None, status_message="")
        self._app: Optional[Application] = None
        self._dialog_control: Optional[FormattedTextControl] = None
        self._dialog_window: Optional[Window] = None
        self._status_control: Optional[FormattedTextControl] = None
        self._input_field: Optional[TextArea] = None
        self._message_area: Optional[TextArea] = None
        self._lock = asyncio.Lock()
        self._dialog_scroll = 0
        self._dialog_visible_count = 10
        self._style = Style.from_dict(
            {
                "frame.border": "#5c5c5c",
                "dialogs": "bg:#202020 #a0a0a0",
                "dialogs.selected": "bg:#3a6ea5 #ffffff bold",
                "messages": "#dddddd",
                "message.outgoing": "#8ef58e",
                "message.incoming": "#89c6ff",
                "message.meta": "italic #888888",
                "status": "reverse",
            }
        )

    async def run(self) -> None:
        """Connect to Telegram and run the interactive UI."""
        await self._service.connect()
        try:
            await self._initialize_state()
            await self._build_application()
            assert self._app is not None  # for mypy
            await self._app.run_async()
        finally:
            await self._service.disconnect()

    async def _initialize_state(self) -> None:
        await self._refresh_dialogs(initial=True)
        dialog = self._current_dialog()
        if dialog:
            await self._load_messages(dialog)
            self._set_status("Connected. Arrows pick chats, Enter to chat, Esc to go back.")
        elif not self._state.status_message:
            self._set_status("Connected, but no dialogs found. Ctrl+R to retry.")

    async def _build_application(self) -> None:
        dialog_kb = KeyBindings()

        @dialog_kb.add("up")
        def _dialog_up(event) -> None:
            asyncio.create_task(self._change_selection(-1))

        @dialog_kb.add("down")
        def _dialog_down(event) -> None:
            asyncio.create_task(self._change_selection(1))

        @dialog_kb.add("enter")
        def _dialog_enter(event) -> None:
            self._focus_input()

        @dialog_kb.add("tab")
        def _dialog_tab(event) -> None:
            self._focus_input()

        @dialog_kb.add("right")
        def _dialog_right(event) -> None:
            self._focus_messages()

        self._dialog_control = FormattedTextControl(
            self._render_dialogs, focusable=True, key_bindings=dialog_kb
        )
        dialog_window_body = Window(
            content=self._dialog_control,
            style="class:dialogs",
            always_hide_cursor=True,
            wrap_lines=False,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        self._dialog_window = dialog_window_body
        dialog_window = Frame(
            dialog_window_body,
            title="Dialogs (Enter/Tab to compose, → to view messages)",
        )

        self._message_area = TextArea(
            text="No messages yet.",
            read_only=True,
            focusable=True,
            scrollbar=True,
            wrap_lines=True,
        )
        message_kb = self._message_area.control.key_bindings

        if message_kb is not None:
            @message_kb.add("left")
            def _message_left(event) -> None:
                self._focus_dialogs()

        messages_window = Frame(
            self._message_area,
            title="Messages (Ctrl+Y for history, ← back to dialogs)",
        )

        self._status_control = FormattedTextControl(self._render_status)

        self._input_field = TextArea(
            prompt="Message> ",
            multiline=False,
            wrap_lines=False,
            accept_handler=self._handle_message_submit,
        )

        root_container = HSplit(
            [
                VSplit([dialog_window, messages_window], padding=1),
                self._input_field,
                Window(
                    height=1,
                    content=self._status_control,
                    style="class:status",
                    always_hide_cursor=True,
                ),
            ]
        )

        kb = KeyBindings()

        @kb.add("c-c")
        @kb.add("c-q")
        def _global_exit(event) -> None:
            event.app.exit()

        @kb.add("c-y")
        def _global_pageup(event) -> None:
            asyncio.create_task(self._load_more_history())

        @kb.add("c-r")
        def _global_reload(event) -> None:
            asyncio.create_task(self._refresh_dialogs(initial=False))

        @kb.add("escape")
        def _global_escape(event) -> None:
            self._focus_dialogs()

        self._app = Application(
            layout=Layout(root_container, focused_element=self._dialog_control),
            key_bindings=kb,
            style=self._style,
            full_screen=True,
            after_render=self._after_render,
        )

    async def _change_selection(self, offset: int) -> None:
        async with self._lock:
            if not self._state.dialogs:
                return
            current = self._state.current_dialog_index or 0
            new_index = max(0, min(len(self._state.dialogs) - 1, current + offset))
            if new_index == current:
                return
            self._state.current_dialog_index = new_index
            dialog = self._state.dialogs[new_index]
            await self._load_messages(dialog)
            self._set_status(f"Switched to {dialog.title}")
            self._ensure_dialog_visible()
            self._refresh_ui()

    async def _refresh_dialogs(self, initial: bool) -> None:
        async with self._lock:
            previous_id = None
            if self._state.current_dialog_index is not None and self._state.dialogs:
                previous_id = self._state.dialogs[self._state.current_dialog_index].dialog_id

            dialogs = await self._service.fetch_dialogs()
            self._state.dialogs = dialogs

            if not dialogs:
                self._state.current_dialog_index = None
                self._state.messages = []
                self._set_status("No dialogs available. Start a chat elsewhere and reload with Ctrl+R.")
                return

            if previous_id is not None:
                for idx, dialog in enumerate(dialogs):
                    if dialog.dialog_id == previous_id:
                        self._state.current_dialog_index = idx
                        break
                else:
                    self._state.current_dialog_index = 0
            else:
                self._state.current_dialog_index = 0

            if not initial:
                dialog = self._current_dialog()
                if dialog:
                    await self._load_messages(dialog)
                    self._set_status(f"Reloaded dialogs. {len(dialogs)} available.")
            self._ensure_dialog_visible()
            self._refresh_ui()

    async def _load_messages(self, dialog: DialogData) -> None:
        messages = await self._service.fetch_messages(dialog, limit=self._message_fetch_limit)
        self._state.messages = messages
        if self._message_area is not None:
            text = self._compose_messages_text(messages)
            doc = Document(text, cursor_position=len(text))
            buffer = self._message_area.buffer
            buffer.set_document(doc, bypass_readonly=True)
            self._message_area.buffer.cursor_position = len(text)
        self._refresh_ui()

    async def _load_more_history(self) -> None:
        async with self._lock:
            dialog = self._current_dialog()
            if dialog is None:
                self._set_status("Nothing selected. Use arrows to choose a chat.")
                return
            self._message_fetch_limit += 25
            await self._load_messages(dialog)
            self._set_status(f"Loaded {len(self._state.messages)} messages.")
            self._ensure_dialog_visible()
            self._refresh_ui()

    async def _send_message(self, text: str) -> None:
        async with self._lock:
            dialog = self._current_dialog()
            if dialog is None:
                self._set_status("No dialog selected. Message discarded.")
                return
            await self._service.send_message(dialog, text)
            await self._load_messages(dialog)
            self._set_status("Message sent.")
            self._refresh_ui()

    def _current_dialog(self) -> Optional[DialogData]:
        if self._state.current_dialog_index is None:
            return None
        if 0 <= self._state.current_dialog_index < len(self._state.dialogs):
            return self._state.dialogs[self._state.current_dialog_index]
        return None

    def _render_dialogs(self) -> List[tuple[str, str]]:
        if not self._state.dialogs:
            return [("class:message.meta", "No dialogs. Ctrl+R to reload.")]

        fragments: List[tuple[str, str]] = []
        height = max(1, self._dialog_visible_count)
        total = len(self._state.dialogs)
        start = min(self._dialog_scroll, max(0, total - height))
        end = min(total, start + height)

        if start > 0:
            fragments.append(("class:message.meta", "↑ older ↑"))
            fragments.append(("", "\n"))

        for idx in range(start, end):
            dialog = self._state.dialogs[idx]
            selected = idx == self._state.current_dialog_index
            marker = "▶" if selected else " "
            style = "class:dialogs.selected" if selected else "class:dialogs"
            fragments.append((style, f"{marker} {dialog.title}"))
            if idx != len(self._state.dialogs) - 1:
                fragments.append(("", "\n"))

        if end < total:
            fragments.append(("", "\n"))
            fragments.append(("class:message.meta", "↓ newer ↓"))
        return fragments

    def _compose_messages_text(self, messages: List[MessageData]) -> str:
        if not messages:
            return "No messages yet. Type to start the conversation."

        rendered: List[str] = []
        for message in messages:
            direction = "->" if message.is_outgoing else "<-"
            timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M")
            content = message.text or ("<media>" if message.has_media else "<empty>")
            lines = content.splitlines() or [""]
            prefix = f"{direction} [{timestamp}] {message.sender}: "
            rendered.append(prefix + lines[0])
            for continuation in lines[1:]:
                rendered.append("    " + continuation)
        return "\n".join(rendered)

    def _render_status(self) -> List[tuple[str, str]]:
        return [("class:status", self._state.status_message)]

    def _handle_message_submit(self, buffer) -> bool:
        text = buffer.text.strip()
        buffer.reset()
        if not text:
            self._set_status("Empty message ignored.")
            return False
        asyncio.create_task(self._send_message(text))
        return False

    def _focus_input(self) -> None:
        if self._app and self._input_field:
            self._app.layout.focus(self._input_field)
            self._set_status("Typing mode. Esc to go back to dialogs.")

    def _focus_messages(self) -> None:
        if self._app and self._message_area:
            self._app.layout.focus(self._message_area)
            self._set_status("Messages focused. Use ↑/↓ to scroll, ← to return.")

    def _focus_dialogs(self) -> None:
        if self._app and self._dialog_control:
            self._app.layout.focus(self._dialog_control)
            self._set_status("Dialog picker active. Use arrows to navigate.")

    def _set_status(self, text: str) -> None:
        self._state.status_message = (
            text + "  •  Ctrl+R reload  •  Ctrl+Y more history  •  Ctrl+C to quit"
        )
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        if self._app:
            self._app.invalidate()

    def _ensure_dialog_visible(self) -> None:
        if self._state.current_dialog_index is None:
            return
        height = max(1, self._dialog_visible_count)
        idx = self._state.current_dialog_index
        if idx < self._dialog_scroll:
            self._dialog_scroll = idx
        elif idx >= self._dialog_scroll + height:
            self._dialog_scroll = idx - height + 1
        max_scroll = max(0, len(self._state.dialogs) - height)
        if self._dialog_scroll > max_scroll:
            self._dialog_scroll = max_scroll

    def _after_render(self, app: Application) -> None:
        if self._dialog_window and self._dialog_window.render_info:
            height = self._dialog_window.render_info.window_height
            if height and height != self._dialog_visible_count:
                self._dialog_visible_count = max(3, height)
                self._ensure_dialog_visible()
