from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.models import utc_now
from app.communication.models import Conversation, Message

ALLOWED_MESSAGE_ROLES = {"system", "user", "assistant", "tool"}


def _clean_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_message_role(value: Any | None, *, default: str = "user") -> str:
    role = (_clean_text(value) or default).lower()
    if role not in ALLOWED_MESSAGE_ROLES:
        raise ValueError(
            f"role must be one of {', '.join(sorted(ALLOWED_MESSAGE_ROLES))}."
        )
    return role


def create_conversation(
    session: Session,
    payload: Mapping[str, Any],
    *,
    created_by_user_id: str | None = None,
) -> Conversation:
    conversation = Conversation(
        title=_clean_text(payload.get("title")) or "Garden chat",
        description=_clean_text(payload.get("description")),
        created_by_user_id=created_by_user_id,
    )
    session.add(conversation)
    session.flush()
    return conversation


def list_conversations(
    session: Session,
    *,
    limit: int = 50,
) -> list[tuple[Conversation, int, datetime | None]]:
    stats = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_message_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = session.execute(
        select(
            Conversation,
            func.coalesce(stats.c.message_count, 0),
            stats.c.last_message_at,
        )
        .outerjoin(stats, stats.c.conversation_id == Conversation.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .limit(limit),
    ).all()
    return [
        (conversation, int(message_count or 0), last_message_at)
        for conversation, message_count, last_message_at in rows
    ]


def get_conversation(session: Session, conversation_id: str) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise LookupError(f"Conversation not found: {conversation_id}")
    return conversation


def list_messages(session: Session, conversation_id: str) -> list[Message]:
    return list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc()),
        ).all(),
    )


def append_message(
    session: Session,
    conversation: Conversation,
    payload: Mapping[str, Any],
    *,
    author_user_id: str | None = None,
) -> Message:
    content = _clean_text(payload.get("content"))
    if content is None:
        raise ValueError("content is required")

    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be an object")

    message = Message(
        conversation_id=conversation.id,
        author_user_id=author_user_id,
        role=normalize_message_role(payload.get("role")),
        content=content,
        metadata_json=dict(metadata),
    )
    session.add(message)
    conversation.updated_at = utc_now()
    session.flush()
    return message


def get_conversation_bundle(
    session: Session,
    conversation_id: str,
) -> tuple[Conversation, list[Message]]:
    conversation = get_conversation(session, conversation_id)
    messages = list_messages(session, conversation_id)
    return conversation, messages
