from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List

from termainaltelegram.models import DialogData, MessageData
from termainaltelegram.service import TelegramServiceProtocol
from termainaltelegram.ui import PromptToolkitChatUI


class PromptFakeService(TelegramServiceProtocol):
    def __init__(self, dialogs: List[DialogData], messages: Dict[int, List[MessageData]]):
        self.dialogs = dialogs
        self.messages = {k: list(v) for k, v in messages.items()}
        self.sent: List[tuple[int, str]] = []

    async def connect(self) -> None:  # pragma: no cover - no-op for tests
        return None

    async def disconnect(self) -> None:  # pragma: no cover - no-op for tests
        return None

    async def fetch_dialogs(self, limit: int = 20) -> List[DialogData]:
        return self.dialogs[:limit]

    async def fetch_messages(self, dialog: DialogData, limit: int = 30) -> List[MessageData]:
        return self.messages.get(dialog.dialog_id, [])[-limit:]

    async def send_message(self, dialog: DialogData, text: str) -> None:
        self.sent.append((dialog.dialog_id, text))
        timestamp = datetime.now(timezone.utc)
        self.messages.setdefault(dialog.dialog_id, []).append(
            MessageData(
                message_id=9999,
                sender="You",
                text=text,
                is_outgoing=True,
                timestamp=timestamp,
                has_media=False,
            )
        )


def sample_message(mid: int, text: str, outgoing: bool) -> MessageData:
    return MessageData(
        message_id=mid,
        sender="Tester" if not outgoing else "You",
        text=text,
        is_outgoing=outgoing,
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        has_media=False,
    )


def test_render_dialogs_highlights_selection():
    dialogs = [
        DialogData(title="Saved", entity="self", dialog_id=1),
        DialogData(title="Friend", entity="friend", dialog_id=2),
        DialogData(title="News", entity="news", dialog_id=3),
    ]
    ui = PromptToolkitChatUI(PromptFakeService(dialogs, {}))
    ui._state.dialogs = dialogs
    ui._state.current_dialog_index = 2
    ui._dialog_visible_count = 2
    ui._dialog_scroll = 1

    fragments = ui._render_dialogs()

    assert any(style == "class:dialogs.selected" and "News" in text for style, text in fragments)


def test_refresh_without_dialogs_sets_status_message():
    service = PromptFakeService([], {})
    ui = PromptToolkitChatUI(service)

    asyncio.run(ui._refresh_dialogs(initial=True))

    assert "No dialogs" in ui._state.status_message
    assert ui._state.current_dialog_index is None


def test_send_message_updates_state_and_service():
    dialogs = [DialogData(title="Saved", entity="self", dialog_id=1)]
    messages = {1: [sample_message(1, "Existing", outgoing=True)]}
    service = PromptFakeService(dialogs, messages)
    ui = PromptToolkitChatUI(service)

    asyncio.run(ui._refresh_dialogs(initial=True))
    dialog = ui._current_dialog()
    assert dialog is not None
    asyncio.run(ui._load_messages(dialog))

    asyncio.run(ui._send_message("Hi there"))

    assert service.sent == [(1, "Hi there")]
    assert ui._state.messages[-1].text == "Hi there"
    assert ui._state.status_message.startswith("Message sent.")


def test_render_messages_handles_multiline():
    ui = PromptToolkitChatUI(PromptFakeService([], {}))
    text = ui._compose_messages_text(
        [
            sample_message(1, "Line one\nLine two", outgoing=False),
            sample_message(2, "Solo", outgoing=True),
        ]
    )

    assert "Line two" in text
    assert "Solo" in text


def test_build_application_handles_missing_key_bindings():
    dialogs = [DialogData(title="Saved", entity="self", dialog_id=1)]
    service = PromptFakeService(dialogs, {})
    ui = PromptToolkitChatUI(service)

    asyncio.run(ui._refresh_dialogs(initial=True))

    # Should not raise when building the application even if text area had no bindings
    asyncio.run(ui._build_application())


def test_load_messages_updates_readonly_textarea():
    dialogs = [DialogData(title="Saved", entity="self", dialog_id=1)]
    messages = {1: [sample_message(1, "Hello world", outgoing=False)]}
    service = PromptFakeService(dialogs, messages)
    ui = PromptToolkitChatUI(service)

    asyncio.run(ui._refresh_dialogs(initial=True))
    asyncio.run(ui._build_application())
    dialog = ui._current_dialog()
    assert dialog is not None

    asyncio.run(ui._load_messages(dialog))

    assert "Hello world" in ui._message_area.text
    assert ui._message_area.buffer.cursor_position == len(ui._message_area.text)
