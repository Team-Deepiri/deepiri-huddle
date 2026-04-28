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

## How to use

### 1) Configure environment

```bash
cp .env.example .env
```

Minimum required:
- pick at least one live LLM path (local Ollama is easiest)
- for local Ollama, keep:
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `OLLAMA_MODEL=gemma2:9b` (or any installed local model)

Optional:
- Discord announcements context:
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_CHANNEL_ID` (optional if channel name lookup works)
  - `DISCORD_ANNOUNCEMENTS_CHANNEL=announcements`

### 2) Generate weekly meeting plans

```bash
# prompts for team if not passed
poetry run huddle plan weekly

# explicit team + next-week
poetry run huddle plan weekly --team ai-ml --week next

# custom meeting type
poetry run huddle plan custom \
  --meeting-title "AI/ML Weekly Risk Review" \
  --meeting-type "risk-review" \
  --team ai-ml \
  --week next
```

Team options:
- `ai-ml`
- `qa`
- `frontend-backend-infra`
- `it`
- `all-teams`

Week options:
- `current`
- `next`

Output files are auto-dated in `plans/`, for example:
- `plans/ai_ml_weekly_status_sync_2026-05-11.md`

### 3) Use the TUI chat agent

```bash
poetry run huddle chat
```

In TUI:
- use quick-action buttons on the left
- type custom prompts in the input bar
- type `clear` to reset transcript

### 4) Typical workflow

```bash
# Monday prep for AI/ML
poetry run huddle plan weekly --team ai-ml --week next

# Open and refine with the chat agent
poetry run huddle chat
```
