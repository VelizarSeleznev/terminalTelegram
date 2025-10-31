from __future__ import annotations

from datetime import datetime, timezone
import asyncio

from termainaltelegram.controller import TerminalController
from termainaltelegram.io import BufferedIO
from termainaltelegram.models import DialogData, MessageData
from termainaltelegram.service import TelegramServiceProtocol


class FakeService(TelegramServiceProtocol):
    def __init__(
        self,
        dialogs: list[DialogData],
        messages: dict[int, list[MessageData]],
        dialog_snapshots: list[list[DialogData]] | None = None,
    ):
        self.dialogs = dialogs
        self.messages = {k: list(v) for k, v in messages.items()}
        self._dialog_snapshots = dialog_snapshots

        self.connected = False
        self.disconnected = False
        self.sent_messages: list[tuple[int, str]] = []
        self.fetch_dialogs_calls = 0
        self.fetch_messages_limits: list[int] = []
        self._next_message_id = 1000

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def fetch_dialogs(self, limit: int = 20):
        self.fetch_dialogs_calls += 1
        if self._dialog_snapshots:
            index = min(self.fetch_dialogs_calls - 1, len(self._dialog_snapshots) - 1)
            self.dialogs = list(self._dialog_snapshots[index])
        return self.dialogs[:limit]

    async def fetch_messages(self, dialog: DialogData, limit: int = 30):
        self.fetch_messages_limits.append(limit)
        history = self.messages.get(dialog.dialog_id, [])
        return history[-limit:]

    async def send_message(self, dialog: DialogData, text: str) -> None:
        self.sent_messages.append((dialog.dialog_id, text))
        message = MessageData(
            message_id=self._next_message_id,
            sender="You",
            text=text,
            is_outgoing=True,
            timestamp=datetime.now(timezone.utc),
            has_media=False,
        )
        self._next_message_id += 1
        self.messages.setdefault(dialog.dialog_id, []).append(message)


def build_message(mid: int, sender: str, text: str, outgoing: bool = False) -> MessageData:
    return MessageData(
        message_id=mid,
        sender=sender,
        text=text,
        is_outgoing=outgoing,
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        has_media=False,
    )


def run_controller(service: FakeService, io: BufferedIO, limit: int = 5) -> None:
    controller = TerminalController(service=service, io=io, message_fetch_limit=limit)
    asyncio.run(controller.start())


def default_dialogs() -> list[DialogData]:
    return [
        DialogData(title="Saved Messages", entity="self", dialog_id=1),
        DialogData(title="Friend", entity="friend", dialog_id=2),
    ]


def default_messages() -> dict[int, list[MessageData]]:
    return {1: [build_message(1, "You", "First note", True)]}


def test_start_shows_dialogs_and_exits():
    io = BufferedIO([":q"])
    service = FakeService(default_dialogs(), default_messages())

    run_controller(service, io)

    assert service.connected and service.disconnected
    assert service.fetch_dialogs_calls == 1
    assert service.fetch_messages_limits == [5]
    assert any("Dialogs:" in line for line in io.outputs)
    assert any("Saved Messages" in line for line in io.outputs)


def test_help_command_lists_available_actions():
    io = BufferedIO([":help", ":q"])
    service = FakeService(default_dialogs(), default_messages())

    run_controller(service, io)

    assert any("Commands:" in line for line in io.outputs)
    assert any(":quit" in line for line in io.outputs)


def test_dialogs_command_marks_active_dialog():
    io = BufferedIO([":dialogs", ":q"])
    service = FakeService(default_dialogs(), default_messages())

    run_controller(service, io)

    assert any("* 0: Saved Messages" in line for line in io.outputs)


def test_switch_and_send_message():
    dialogs = [
        DialogData(title="Saved Messages", entity="self", dialog_id=1),
        DialogData(title="@tima_tima", entity="tima", dialog_id=2),
    ]
    messages = {
        1: [build_message(1, "You", "Pinned note", True)],
        2: [build_message(10, "tima", "Hello!", False)],
    }
    io = BufferedIO([":1", "Hi there", ":q"])
    service = FakeService(dialogs, messages)

    run_controller(service, io)

    assert service.sent_messages == [(2, "Hi there")]
    assert service.fetch_messages_limits.count(5) >= 2
    assert any("Hi there" in line for line in io.outputs)


def test_more_command_increases_limit():
    io = BufferedIO([":more", ":q"])
    service = FakeService(default_dialogs(), default_messages())

    run_controller(service, io)

    assert service.fetch_messages_limits == [5, 30]


def test_reload_fetches_dialogs_again():
    new_dialogs = default_dialogs() + [DialogData(title="New chat", entity="new", dialog_id=3)]
    io = BufferedIO([":reload", ":q"])
    service = FakeService(
        default_dialogs(),
        default_messages(),
        dialog_snapshots=[default_dialogs(), new_dialogs],
    )

    run_controller(service, io)

    assert service.fetch_dialogs_calls == 2
    assert any("New chat" in line for line in io.outputs)


def test_unknown_command_reports_error():
    io = BufferedIO([":bogus", ":q"])
    service = FakeService(default_dialogs(), default_messages())

    run_controller(service, io)

    assert any("Unknown command: :bogus" in line for line in io.outputs)


def test_open_invalid_index_reports():
    io = BufferedIO([":open 42", ":q"])
    service = FakeService(default_dialogs(), default_messages())

    run_controller(service, io)

    assert any("Invalid dialog index: 42" in line for line in io.outputs)


def test_send_when_no_dialog_selected_warns_user():
    io = BufferedIO(["Hello there", ":q"])
    service = FakeService([], {})

    run_controller(service, io)

    assert any("Choose a dialog" in line for line in io.outputs)
