import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from bridge_log import log_bridge_event

load_dotenv()

MODEL_PREFS_FILE = Path(".telegram_model_prefs.json")

HAIKU_MODEL = os.environ.get("ANTHROPIC_MODEL_HAIKU", "claude-3-haiku-20240307")
OPUS_MODEL = os.environ.get("ANTHROPIC_MODEL_OPUS", "claude-opus-4-1-20250805")
DEFAULT_MODEL_MODE = os.environ.get("DEFAULT_TELEGRAM_MODEL", "haiku")
BOT_NAME = os.environ.get("BOT_NAME", "Chopper")
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID")


def load_model_prefs():
    if not MODEL_PREFS_FILE.exists():
        return {}
    try:
        return json.loads(MODEL_PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_model_prefs(prefs):
    MODEL_PREFS_FILE.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def get_chat_mode(chat_id: int, prefs: dict) -> str:
    return prefs.get(str(chat_id), DEFAULT_MODEL_MODE)


def resolve_model_name(mode: str) -> str:
    return OPUS_MODEL if mode == "opus" else HAIKU_MODEL


def get_anthropic_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")
    return Anthropic(api_key=api_key)


def is_allowed_user(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    if not update.effective_user:
        return False
    return str(update.effective_user.id) == str(ALLOWED_USER_ID)


async def ensure_allowed(update: Update) -> bool:
    if is_allowed_user(update):
        return True
    await update.message.reply_text("Access denied for this bot.")
    return False


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    await update.message.reply_text(
        f"[{BOT_NAME}]: Ready. Use /haiku or /opus to switch models, /model to check current mode, and then send any message."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    await update.message.reply_text(
        "Commands:\n"
        "/haiku - Switch to Haiku model\n"
        "/opus - Switch to Opus model\n"
        "/model - Show current model mode\n"
        "/model haiku - Set Haiku model\n"
        "/model opus - Set Opus model\n"
        "/commands - Show command list\n"
        "/start - Initialize bot"
    )


async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    await help_cmd(update, context)


async def set_mode(update: Update, mode: str):
    prefs = load_model_prefs()
    chat_id = update.effective_chat.id
    prefs[str(chat_id)] = mode
    save_model_prefs(prefs)
    model_name = resolve_model_name(mode)
    log_bridge_event(
        source="telegram",
        event="model_switch",
        session_id=f"tg:{chat_id}",
        user_id=update.effective_user.id if update.effective_user else None,
        chat_id=chat_id,
        model=model_name,
        detail=f"mode={mode}"
    )
    await update.message.reply_text(f"[{BOT_NAME}]: Model set to {mode} ({model_name}).")


async def haiku_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    await set_mode(update, "haiku")


async def opus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    await set_mode(update, "opus")


async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    if context.args:
        arg = context.args[0].strip().lower()
        if arg in {"haiku", "opus"}:
            await set_mode(update, arg)
            return
        await update.message.reply_text(f"[{BOT_NAME}]: Unknown model '{arg}'. Use haiku or opus.")
        return

    prefs = load_model_prefs()
    mode = get_chat_mode(update.effective_chat.id, prefs)
    model_name = resolve_model_name(mode)
    await update.message.reply_text(f"[{BOT_NAME}]: Current model is {mode} ({model_name}).")


def build_system_prompt() -> str:
    return (
        f"You are {BOT_NAME}, an AI assistant created for Ask Chopper. "
        "Be helpful, accurate, and concise. Always prefix your final answer with [Chopper]:"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return
    if not update.message or not update.message.text:
        return

    prefs = load_model_prefs()
    mode = get_chat_mode(update.effective_chat.id, prefs)
    model_name = resolve_model_name(mode)
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None

    log_bridge_event(
        source="telegram",
        event="telegram_inbound_message",
        session_id=f"tg:{chat_id}",
        user_id=user_id,
        chat_id=chat_id,
        model=model_name,
        message=update.message.text,
        extra={"mode": mode}
    )

    client = get_anthropic_client()
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=1200,
            temperature=0.7,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": update.message.text}],
        )
    except Exception as exc:
        # If selected model is unavailable, fall back to Haiku automatically.
        if "not_found_error" in str(exc) or "model:" in str(exc):
            fallback_model = HAIKU_MODEL
            log_bridge_event(
                source="telegram",
                event="telegram_model_fallback",
                status="error",
                session_id=f"tg:{chat_id}",
                user_id=user_id,
                chat_id=chat_id,
                model=model_name,
                detail=str(exc),
                extra={"fallback_model": fallback_model}
            )
            try:
                response = client.messages.create(
                    model=fallback_model,
                    max_tokens=1200,
                    temperature=0.7,
                    system=build_system_prompt(),
                    messages=[{"role": "user", "content": update.message.text}],
                )
                await update.message.reply_text(
                    f"[{BOT_NAME}]: Selected model '{model_name}' is unavailable. "
                    f"Falling back to Haiku ({fallback_model})."
                )
            except Exception as fallback_exc:
                log_bridge_event(
                    source="telegram",
                    event="telegram_response_error",
                    status="error",
                    session_id=f"tg:{chat_id}",
                    user_id=user_id,
                    chat_id=chat_id,
                    model=fallback_model,
                    detail=str(fallback_exc)
                )
                await update.message.reply_text(f"[{BOT_NAME}]: Error: {fallback_exc}")
                return
        else:
            log_bridge_event(
                source="telegram",
                event="telegram_response_error",
                status="error",
                session_id=f"tg:{chat_id}",
                user_id=user_id,
                chat_id=chat_id,
                model=model_name,
                detail=str(exc)
            )
            await update.message.reply_text(f"[{BOT_NAME}]: Error: {exc}")
            return
    try:
        text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        response_text = "".join(text_parts).strip()
        if not response_text.startswith("[Chopper]:"):
            response_text = f"[Chopper]: {response_text}"
        log_bridge_event(
            source="telegram",
            event="telegram_response",
            session_id=f"tg:{chat_id}",
            user_id=user_id,
            chat_id=chat_id,
            model=getattr(response, "model", model_name),
            detail=response_text,
            extra={
                "input_tokens": getattr(getattr(response, "usage", None), "input_tokens", None),
                "output_tokens": getattr(getattr(response, "usage", None), "output_tokens", None),
            }
        )
        await update.message.reply_text(response_text)
    except Exception as exc:
        log_bridge_event(
            source="telegram",
            event="telegram_response_error",
            status="error",
            session_id=f"tg:{chat_id}",
            user_id=user_id,
            chat_id=chat_id,
            model=model_name,
            detail=str(exc)
        )
        await update.message.reply_text(f"[{BOT_NAME}]: Error: {exc}")


async def set_telegram_commands(app):
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Initialize the bot"),
            BotCommand("haiku", "Use Haiku model"),
            BotCommand("opus", "Use Opus model"),
            BotCommand("model", "Show or set model"),
            BotCommand("commands", "Show command list"),
            BotCommand("help", "Show help"),
        ]
    )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured in .env")

    app = ApplicationBuilder().token(token).post_init(set_telegram_commands).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("commands", commands_cmd))
    app.add_handler(CommandHandler("haiku", haiku_cmd))
    app.add_handler(CommandHandler("opus", opus_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
