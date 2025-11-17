from __future__ import annotations

import re
from typing import List

from database import db
from Models.LLMMemory import LLMMemory

# The LLMMemory.info column is limited to 5000 characters.
# We keep a comfortable reserve to avoid hitting that limit on commit.
MAX_MEMORY_CHARS = 4000
# When we need to shrink the stored context we aim for this size.
SUMMARY_TARGET_CHARS = 2500
# Each interaction snippet that we append to the memory shouldn't be huge on its own.
SNIPPET_MAX_CHARS = 600


def _clean_text(value: str) -> str:
    """Normalize whitespace to keep the memory compact."""
    return re.sub(r"\s+", " ", value).strip()


def _combine_infos(memories: List[LLMMemory]) -> str:
    parts = []
    for memory in memories:
        if memory.info:
            parts.append(memory.info.strip())
    return "\n".join(parts).strip()


def summarize_text(text: str, target_chars: int = SUMMARY_TARGET_CHARS) -> str:
    """A lightweight extractive summarizer based on sentence truncation.

    We avoid calling external LLMs so the API keeps working offline.
    The function keeps as many leading sentences as possible and falls back to
    a hard cut if there are no sentence boundaries.
    """
    if len(text) <= target_chars:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary_parts = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        tentative = (" ".join(summary_parts + [sentence])).strip()
        if len(tentative) > target_chars:
            break
        summary_parts.append(sentence)

    if not summary_parts:
        return text[:target_chars].rstrip()

    summary = " ".join(summary_parts).strip()
    if len(summary) > target_chars:
        summary = summary[:target_chars].rstrip()
    return summary


def get_user_memory_context(user_id: int, max_chars: int = MAX_MEMORY_CHARS) -> str:
    """Return a compact long-term memory context for the user."""
    memories = (
        LLMMemory.query.filter_by(user_id=user_id)
        .order_by(LLMMemory.id.asc())
        .all()
    )
    if not memories:
        return ""

    combined = _combine_infos(memories)
    if len(combined) > max_chars:
        combined = summarize_text(combined, target_chars=max_chars)
    return combined


def build_memory_snippet(user_message: str, assistant_message: str) -> str:
    """Create a succinct snippet from the latest interaction."""
    user_chunk = _clean_text(user_message) if user_message else ""
    assistant_chunk = _clean_text(assistant_message) if assistant_message else ""

    if not user_chunk and not assistant_chunk:
        return ""

    snippet = (
        f"Пользователь сообщил: {user_chunk}. "
        f"Ассистент ответил: {assistant_chunk}."
    ).strip()

    if len(snippet) > SNIPPET_MAX_CHARS:
        snippet = snippet[: SNIPPET_MAX_CHARS - 3].rstrip() + "..."
    return snippet


def update_user_memory(user_id: int, new_info: str) -> None:
    """Append a new piece of information to the user's long-term memory."""
    if not new_info:
        return

    new_info = _clean_text(new_info)
    if not new_info:
        return

    memories = (
        LLMMemory.query.filter_by(user_id=user_id)
        .order_by(LLMMemory.id.asc())
        .all()
    )

    if not memories:
        memory = LLMMemory(user_id=user_id, info=new_info[:MAX_MEMORY_CHARS])
        db.session.add(memory)
        db.session.commit()
        return

    primary = memories[0]
    extra_texts = [m.info for m in memories[1:] if m.info]

    # We keep a single compact record to avoid unlimited growth of rows.
    for redundant in memories[1:]:
        db.session.delete(redundant)

    combined = _combine_infos([primary])
    payload = "\n".join(part for part in [combined, *extra_texts, new_info] if part).strip()

    if len(payload) > MAX_MEMORY_CHARS:
        payload = summarize_text(payload, target_chars=MAX_MEMORY_CHARS)

    primary.info = payload
    db.session.commit()

__all__ = [
    "build_memory_snippet",
    "get_user_memory_context",
    "summarize_text",
    "update_user_memory",
]