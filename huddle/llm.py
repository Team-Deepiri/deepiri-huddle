from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx

from huddle.config import Settings


@dataclass(slots=True)
class LlmResult:
    text: str
    provider: str
    model: str


ProviderHandler = Callable[[httpx.Client, Settings, str], LlmResult]


class MultiProviderLlm:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._handlers: dict[str, ProviderHandler] = {
            "ollama": self._call_ollama,
            "deepseek": self._call_deepseek,
            "gemini": self._call_gemini,
            "google": self._call_gemini,
            "openrouter": self._call_openrouter,
            "openai": self._call_openai,
        }

    def generate(self, prompt: str) -> LlmResult:
        errors: list[str] = []
        with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
            for provider in self.settings.provider_order():
                handler = self._handlers.get(provider)
                if not handler:
                    errors.append(f"unknown provider '{provider}'")
                    continue
                try:
                    return handler(client, self.settings, prompt)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{provider}: {exc}")
        raise RuntimeError("all LLM providers failed: " + " | ".join(errors))

    @staticmethod
    def _call_ollama(client: httpx.Client, settings: Settings, prompt: str) -> LlmResult:
        response = client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        response.raise_for_status()
        text = response.json()["message"]["content"]
        return LlmResult(text=text, provider="ollama", model=settings.ollama_model)

    @staticmethod
    def _call_deepseek(client: httpx.Client, settings: Settings, prompt: str) -> LlmResult:
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY missing")
        response = client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return LlmResult(text=text, provider="deepseek", model=settings.deepseek_model)

    @staticmethod
    def _call_gemini(client: httpx.Client, settings: Settings, prompt: str) -> LlmResult:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY missing")
        model_id = settings.gemini_model
        if not model_id.startswith("models/"):
            model_id = f"models/{model_id}"
        response = client.post(
            f"https://generativelanguage.googleapis.com/v1beta/{model_id}:generateContent",
            params={"key": settings.google_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return LlmResult(text=text, provider="gemini", model=settings.gemini_model)

    @staticmethod
    def _call_openrouter(client: httpx.Client, settings: Settings, prompt: str) -> LlmResult:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY missing")
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://deepiri.local",
                "X-Title": "deepiri-huddle",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return LlmResult(text=text, provider="openrouter", model=settings.openrouter_model)

    @staticmethod
    def _call_openai(client: httpx.Client, settings: Settings, prompt: str) -> LlmResult:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY missing")
        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return LlmResult(text=text, provider="openai", model=settings.openai_model)

