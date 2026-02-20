# Telegram Commands

This bot uses Anthropic models and supports runtime model switching.

## Commands

- `/start`: Initialize the bot and show usage.
- `/help`: Show command help.
- `/commands`: Alias for command help.
- `/haiku`: Switch current chat to Haiku model.
- `/opus`: Switch current chat to Opus model.
- `/model`: Show current selected model for the chat.
- `/model haiku`: Set model to Haiku.
- `/model opus`: Set model to Opus.

## Model behavior

- Default model mode is `haiku`.
- Model selection is stored per-chat in `.telegram_model_prefs.json`.
- Responses keep the `[Chopper]:` prefix.

## Required environment variables

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL_HAIKU`
- `ANTHROPIC_MODEL_OPUS`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_ID` (optional but recommended)
- `BOT_NAME`
