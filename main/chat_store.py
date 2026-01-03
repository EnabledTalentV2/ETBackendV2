from typing import List, Dict
from main.models import ChatSession, ChatMessage


def get_or_create_session(
    *,
    session_id=None,
    mode: str,
    user_id=None,
    candidate_slug=None,
):
    if session_id:
        return ChatSession.objects.get(id=session_id)

    return ChatSession.objects.create(
        mode=mode,
        user_id=user_id,
        candidate_slug=candidate_slug,
    )


def load_history(session: ChatSession) -> List[Dict[str, str]]:
    return [
        {"role": msg.role, "content": msg.content}
        for msg in session.messages.all()
    ]


def save_message(session: ChatSession, role: str, content: str):
    ChatMessage.objects.create(
        session=session,
        role=role,
        content=content,
    )
