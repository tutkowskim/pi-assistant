from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.db.session import engine
from app.services.conversations import (
    backfill_default_conversation_titles,
    title_from_prompt,
)


def test_title_from_prompt_truncates_at_a_word_boundary() -> None:
    title = title_from_prompt(
        "Explain how atmospheric scattering produces the colors visible during a dramatic sunset"
    )

    assert title == "Explain how atmospheric scattering produces the colors…"
    assert len(title) <= 60


def test_existing_default_title_is_backfilled_from_first_prompt() -> None:
    with Session(engine) as session:
        conversation = Conversation()
        session.add(conversation)
        session.flush()
        session.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="First question",
                ),
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Later question",
                ),
            ]
        )
        session.commit()
        conversation_id = conversation.id

    backfill_default_conversation_titles()

    with Session(engine) as session:
        assert session.get(Conversation, conversation_id).title == "First question"  # type: ignore[union-attr]
