from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.db.session import SessionLocal

DEFAULT_CONVERSATION_TITLE = "New conversation"
MAX_GENERATED_TITLE_LENGTH = 60


def is_default_conversation_title(title: str) -> bool:
    return title.strip().casefold() == DEFAULT_CONVERSATION_TITLE.casefold()


def title_from_prompt(prompt: str) -> str:
    normalized = " ".join(prompt.split())
    if len(normalized) <= MAX_GENERATED_TITLE_LENGTH:
        return normalized

    prefix = normalized[: MAX_GENERATED_TITLE_LENGTH - 1]
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    prefix = prefix.rstrip(" ,.;:-")
    return f"{prefix}…"


def set_title_from_prompt(
    session: Session, conversation: Conversation, prompt: str
) -> None:
    if is_default_conversation_title(conversation.title):
        conversation.title = title_from_prompt(prompt)


def backfill_default_conversation_titles() -> None:
    with SessionLocal.begin() as session:
        conversations = session.scalars(
            select(Conversation).where(
                func.lower(func.trim(Conversation.title))
                == DEFAULT_CONVERSATION_TITLE.casefold()
            )
        ).all()
        for conversation in conversations:
            first_prompt = session.scalar(
                select(Message.content)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.role == "user",
                )
                .order_by(Message.created_at.asc())
                .limit(1)
            )
            if first_prompt:
                set_title_from_prompt(session, conversation, first_prompt)
