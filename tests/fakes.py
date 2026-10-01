"""Minimal stand-ins for the Telegram objects a handler touches.

Using fakes rather than the real classes keeps handler tests fast and offline,
and makes what a handler actually did observable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SentMessage:
    text: str | None = None
    reply_markup: Any = None
    photo: bytes | None = None
    document: Any = None
    filename: str | None = None
    caption: str | None = None


@dataclass
class FakeUser:
    id: int = 1
    language_code: str | None = "en"
    is_bot: bool = False


@dataclass
class FakeChat:
    id: int = 1


@dataclass
class FakeMessage:
    text: str | None = None
    sent: list[SentMessage] = field(default_factory=list)

    async def reply_text(self, text: str, **kwargs: Any) -> SentMessage:
        message = SentMessage(text=text, reply_markup=kwargs.get("reply_markup"))
        self.sent.append(message)
        return message

    async def reply_photo(self, photo: bytes, **kwargs: Any) -> SentMessage:
        message = SentMessage(photo=photo, caption=kwargs.get("caption"))
        self.sent.append(message)
        return message

    async def reply_document(self, document: Any, **kwargs: Any) -> SentMessage:
        message = SentMessage(
            document=document.getvalue() if hasattr(document, "getvalue") else document,
            filename=kwargs.get("filename"),
            caption=kwargs.get("caption"),
        )
        self.sent.append(message)
        return message


@dataclass
class FakeCallbackQuery:
    data: str | None = None
    edits: list[SentMessage] = field(default_factory=list)
    answered: bool = False

    async def answer(self, *args: Any, **kwargs: Any) -> None:
        self.answered = True

    async def edit_message_text(self, text: str, **kwargs: Any) -> None:
        self.edits.append(SentMessage(text=text, reply_markup=kwargs.get("reply_markup")))


@dataclass
class FakeUpdate:
    effective_user: FakeUser = field(default_factory=FakeUser)
    effective_chat: FakeChat = field(default_factory=FakeChat)
    message: FakeMessage | None = None
    callback_query: FakeCallbackQuery | None = None


@dataclass
class FakeBot:
    sent: list[tuple[int, str]] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    commands: list[tuple[str | None, list[Any]]] = field(default_factory=list)

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> None:
        self.sent.append((chat_id, text))

    async def send_chat_action(self, chat_id: int, action: str, **kwargs: Any) -> None:
        self.actions.append(action)

    async def set_my_commands(self, commands: list[Any], **kwargs: Any) -> None:
        self.commands.append((kwargs.get("language_code"), commands))


@dataclass
class FakeContext:
    user_data: dict[str, Any] = field(default_factory=dict)
    chat_data: dict[str, Any] = field(default_factory=dict)
    bot: FakeBot = field(default_factory=FakeBot)
    application: Any = None
    error: BaseException | None = None


def command(text: str, user_id: int = 1, language_code: str | None = "en") -> FakeUpdate:
    return FakeUpdate(
        effective_user=FakeUser(id=user_id, language_code=language_code),
        effective_chat=FakeChat(id=user_id),
        message=FakeMessage(text=text),
    )


def tap(data: str, user_id: int = 1) -> FakeUpdate:
    return FakeUpdate(
        effective_user=FakeUser(id=user_id),
        effective_chat=FakeChat(id=user_id),
        callback_query=FakeCallbackQuery(data=data),
    )


def text_of(message: SentMessage) -> str:
    """Assert a message carried text and return it, for use in assertions."""
    assert message.text is not None, "expected a text message"
    return message.text
