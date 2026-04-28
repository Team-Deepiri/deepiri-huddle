from __future__ import annotations

from dataclasses import dataclass

import httpx

from huddle.config import Settings
from huddle.llm import MultiProviderLlm


@dataclass(slots=True)
class DiscordMessage:
    author: str
    timestamp: str
    content: str


class DiscordFeed:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enabled(self) -> bool:
        return bool(self.settings.discord_bot_token)

    def _resolve_channel_id(self, client: httpx.Client) -> str | None:
        if self.settings.discord_channel_id:
            return self.settings.discord_channel_id
        target = self.settings.discord_announcements_channel.strip().lower().lstrip("#")
        guilds = client.get(
            "https://discord.com/api/v10/users/@me/guilds",
            headers={"Authorization": f"Bot {self.settings.discord_bot_token}"},
        )
        guilds.raise_for_status()
        for guild in guilds.json():
            channels = client.get(
                f"https://discord.com/api/v10/guilds/{guild['id']}/channels",
                headers={"Authorization": f"Bot {self.settings.discord_bot_token}"},
            )
            if channels.status_code != 200:
                continue
            for channel in channels.json():
                if channel.get("type") != 0:
                    continue
                if (channel.get("name") or "").strip().lower() == target:
                    return channel["id"]
        return None

    def latest_messages(self) -> list[DiscordMessage]:
        if not self.enabled():
            return []
        with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
            channel_id = self._resolve_channel_id(client)
            if not channel_id:
                return []
            response = client.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                params={"limit": self.settings.discord_fetch_limit},
                headers={"Authorization": f"Bot {self.settings.discord_bot_token}"},
            )
            response.raise_for_status()
            raw = response.json()
        messages: list[DiscordMessage] = []
        for item in reversed(raw):
            content = (item.get("content") or "").strip()
            if not content:
                continue
            messages.append(
                DiscordMessage(
                    author=item.get("author", {}).get("username", "unknown"),
                    timestamp=item.get("timestamp", ""),
                    content=content,
                )
            )
        return messages

    def summarized_context(self, llm: MultiProviderLlm) -> str:
        messages = self.latest_messages()
        if not messages:
            return "No Discord announcements available."
        rendered = "\n".join(f"- {m.timestamp} | {m.author}: {m.content[:400]}" for m in messages[-20:])
        prompt = (
            "Summarize these Discord #announcements updates for a weekly engineering meeting agenda.\n"
            "Return markdown with heading '## Discord Announcements Summary' and 4-8 concise bullets.\n\n"
            f"{rendered}"
        )
        try:
            return llm.generate(prompt).text.strip()
        except Exception:
            bullets = "\n".join(f"- {m.author}: {m.content}" for m in messages[-8:])
            return "## Discord Announcements Summary\n" + bullets

