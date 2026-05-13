from __future__ import annotations

import logging

from huddle.discord_feed import DiscordFeed
from huddle.llm import MultiProviderLlm
from huddle.memory import MemoryStore

log = logging.getLogger(__name__)


class ChatAgent:
    def __init__(
        self,
        llm: MultiProviderLlm,
        memory: MemoryStore,
        discord_feed: DiscordFeed,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.discord_feed = discord_feed

    def reply(self, user_message: str) -> str:
        self.memory.append("user", user_message)
        history = self.memory.latest(limit=10)
        history_md = "\n".join(f"- {h.role}: {h.content[:220]}" for h in history)
        discord_ctx = "Not requested."
        if "discord" in user_message.lower() or "announcement" in user_message.lower():
            try:
                discord_ctx = self.discord_feed.summarized_context(self.llm)
            except Exception:
                discord_ctx = "Discord unavailable."
        prompt = f"""
You are deepiri-huddle assistant.
Conversation memory:
{history_md}

Discord context:
{discord_ctx}

User request:
{user_message}

Respond with practical actions and outputs.
"""
        try:
            result = self.llm.generate(prompt)
            text = result.text.strip()
            log.info(
                "chat_llm_reply_ok provider=%s model=%s chars=%s",
                result.provider,
                result.model,
                len(text),
            )
        except Exception as exc:
            log.warning(
                "chat_llm_unavailable_using_static_reply error_type=%s error=%s",
                type(exc).__name__,
                str(exc)[:800],
                exc_info=log.isEnabledFor(logging.DEBUG),
            )
            text = (
                "LLM unavailable. You can still run `huddle plan weekly` "
                "for deterministic plan output."
            )
        self.memory.append("assistant", text)
        return text

