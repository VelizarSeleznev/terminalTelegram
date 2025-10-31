from __future__ import annotations

import asyncio
from typing import List, Optional, Protocol

try:  # pragma: no cover - import guard for optional dependency
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
except ImportError:  # pragma: no cover - handled gracefully at runtime
    TelegramClient = None  # type: ignore[assignment]
    SessionPasswordNeededError = None  # type: ignore[assignment]

from .io import IOInterface
from .models import DialogData, MessageData


class TelegramServiceProtocol(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def fetch_dialogs(self, limit: int = 20) -> List[DialogData]: ...

    async def fetch_messages(self, dialog: DialogData, limit: int = 30) -> List[MessageData]: ...

    async def send_message(self, dialog: DialogData, text: str) -> None: ...


class TelethonService(TelegramServiceProtocol):
    """Adapter that converts Telethon objects into lightweight dataclasses."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        io: IOInterface,
    ):
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_name = session_name
        self._io = io
        self._client: Optional[TelegramClient] = None
        self._me_display: str = "You"

    async def connect(self) -> None:
        if TelegramClient is None:
            raise RuntimeError("Telethon is not installed. Install it with `pip install telethon`.")
        if self._client is not None:
            return

        self._client = TelegramClient(self._session_name, self._api_id, self._api_hash)
        await self._client.connect()
        if not await self._client.is_user_authorized():
            await self._perform_login()
        me = await self._client.get_me()
        if me:
            self._me_display = me.first_name or me.username or "You"

    async def disconnect(self) -> None:
        if self._client is None:
            return
        await self._client.disconnect()
        self._client = None

    async def fetch_dialogs(self, limit: int = 20) -> List[DialogData]:
        client = self._require_client()
        dialogs = await client.get_dialogs(limit=limit)
        result: List[DialogData] = []
        for dialog in dialogs:
            title = dialog.title or "Unknown chat"
            dialog_id = getattr(dialog.entity, "id", dialog.id)
            result.append(DialogData(title=title, entity=dialog.entity, dialog_id=dialog_id))
        return result

    async def fetch_messages(self, dialog: DialogData, limit: int = 30) -> List[MessageData]:
        client = self._require_client()
        messages = await client.get_messages(dialog.entity, limit=limit)
        items: List[MessageData] = []
        for message in reversed(messages):
            sender_name = self._determine_sender_name(message, dialog_title=dialog.title)
            text = message.message or ""
            items.append(
                MessageData(
                    message_id=message.id,
                    sender=sender_name,
                    text=text,
                    is_outgoing=bool(message.out),
                    timestamp=message.date,
                    has_media=bool(message.media),
                )
            )
        return items

    async def send_message(self, dialog: DialogData, text: str) -> None:
        client = self._require_client()
        await client.send_message(dialog.entity, text)

    async def _perform_login(self) -> None:
        client = self._require_client()
        phone = await self._prompt("Enter your phone number (international format): ")
        await client.send_code_request(phone)
        code = await self._prompt("Enter the login code you received: ")
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            password = await self._prompt("Two-step password: ", hide_input=True)
            await client.sign_in(password=password)

    async def _prompt(self, prompt: str, hide_input: bool = False) -> str:
        if hide_input:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._secret_input, prompt)
        return self._io.read(prompt)

    def _secret_input(self, prompt: str) -> str:
        # Deferred import to avoid pulling getpass for tests
        from getpass import getpass

        return getpass(prompt)

    def _determine_sender_name(self, message, dialog_title: str) -> str:
        if bool(message.out):
            return self._me_display
        sender = getattr(message, "sender", None)
        if sender:
            for attr in ("first_name", "last_name", "username", "title"):
                value = getattr(sender, attr, None)
                if value:
                    return value
        return dialog_title

    def _require_client(self) -> TelegramClient:
        if self._client is None:
            raise RuntimeError("Telegram client is not connected")
        return self._client
