from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DialogData:
    """Lightweight dialog representation used by the terminal UI."""

    title: str
    entity: Any
    dialog_id: int


@dataclass(slots=True)
class MessageData:
    """Lightweight message representation used by the terminal UI."""

    message_id: int
    sender: str
    text: str
    is_outgoing: bool
    timestamp: datetime
    has_media: bool = False
