# deepiri-huddle

AI meeting-planning agent for Deepiri.

- Team-aware weekly/custom plans
- Date-based output filenames
- Next-week planning support
- Discord `#announcements` context support
- Local memory
- Multi-provider LLM fallback (Ollama, DeepSeek, Gemini, OpenRouter, OpenAI)
- Full-screen TUI chat

## Quick start

```bash
cd deepiri-huddle
poetry install
poetry run huddle plan weekly
poetry run huddle plan weekly --week next
poetry run huddle chat
```
