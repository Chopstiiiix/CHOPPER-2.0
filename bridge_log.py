import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

_write_lock = Lock()


def get_bridge_log_path() -> Path:
    configured_path = os.environ.get("CHOPPER_BRIDGE_LOG_FILE", "").strip()
    if configured_path:
        return Path(configured_path).expanduser()
    return Path(__file__).resolve().parent / "logs" / "bridge.log"


def _truncate(value: Optional[str], max_len: int = 400) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}...<truncated>"


def log_bridge_event(
    *,
    source: str,
    event: str,
    status: str = "ok",
    session_id: Optional[str] = None,
    user_id: Optional[Any] = None,
    chat_id: Optional[Any] = None,
    model: Optional[str] = None,
    message: Optional[str] = None,
    detail: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "event": event,
        "status": status,
        "session_id": session_id,
        "user_id": str(user_id) if user_id is not None else None,
        "chat_id": str(chat_id) if chat_id is not None else None,
        "model": model,
        "message": _truncate(message),
        "detail": _truncate(detail),
        "extra": extra or {},
    }

    try:
        log_path = get_bridge_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True) + "\n"
        with _write_lock:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        # Never fail primary app/bot flow because of logging.
        return


def read_bridge_logs(limit: int = 200) -> Dict[str, Any]:
    safe_limit = max(1, min(int(limit), 1000))
    log_path = get_bridge_log_path()

    if not log_path.exists():
        return {"path": str(log_path), "entries": []}

    entries = []
    with log_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()[-safe_limit:]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"path": str(log_path), "entries": entries}
