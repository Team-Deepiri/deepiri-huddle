from __future__ import annotations

from huddle.discord_feed import DiscordFeed
from huddle.llm import MultiProviderLlm
from huddle.memory import MemoryStore


class ChatAgent:
    def __init__(
        self, llm: MultiProviderLlm, memory: MemoryStore, discord_feed: DiscordFeed
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
            text = self.llm.generate(prompt).text.strip()
        except Exception:
            text = (
                "LLM unavailable. Try `huddle plan weekly`"
                " for heuristic/template-based plan output."
            )
        self.memory.append("assistant", text)
        return text
