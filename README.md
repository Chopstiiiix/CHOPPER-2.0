# Chopper

Chopper is a Flask-based AI assistant with:
- web chat (login required),
- document-aware chat (RAG via Chroma),
- support chat with human admin messaging,
- Telegram bot integration with slash commands for model switching (`haiku`/`opus`).

## Core behavior

- `/` redirects to `/app`.
- `/app` requires authentication and loads the chat UI.
- Assistant replies are prefixed with `[Chopper]:`.
- Base model is Haiku, with Opus available as a selectable option.
- Human support chat and admin response flows remain enabled.

## Requirements

- Python 3.9+
- Dependencies in `requirements.txt`
- Anthropic API key
- Chroma Cloud credentials for document retrieval
- Telegram bot token (if using Telegram bot)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` from `.env.example` and set:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` / `ANTHROPIC_MODEL_HAIKU` / `ANTHROPIC_MODEL_OPUS`
- `BOT_ID` / `BOT_NAME`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ALLOWED_USER_ID`
- DB and Chroma variables

3. Run web app:
```bash
python3 app.py
```

4. Run Telegram bot:
```bash
python3 telegram_bot.py
```

## Telegram commands

- `/start` initialize bot
- `/haiku` switch to Haiku model
- `/opus` switch to Opus model
- `/model` show current model
- `/model haiku` set Haiku
- `/model opus` set Opus
- `/commands` list commands

## Routes kept

- `/`, `/app`
- `/register`, `/login`, `/logout`
- `/chat`, `/chat-with-document`
- `/api/chat/history`
- `/api/documents`, `/api/documents/<id>`, `/api/documents/clear`
- `/api/support-chat`, `/api/support-chat/unread`
- `/admin`, `/admin/chat/<user_id>`, `/api/admin/reply`, `/api/admin/unread-count`

## Notes

- Document embeddings are generated locally via SentenceTransformers.
- Chroma stores chunk vectors and metadata for retrieval and citation.
- Support chat remains separate from AI assistant chat.
