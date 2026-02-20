#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
INSTANCE = ROOT / "instance"
MEMORY_FILE = INSTANCE / "agent-memory.json"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def count_patterns(text: str):
    lower = text.lower()
    return {
        "errors": lower.count("error"),
        "warnings": lower.count("warn"),
        "requests": lower.count("request"),
    }


def load_memory():
    if not MEMORY_FILE.exists():
        return {}
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def system_health():
    return {
        "cwd": str(ROOT),
        "python": os.sys.version.split()[0],
        "time_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_report() -> str:
    log_counts = {"errors": 0, "warnings": 0, "requests": 0}
    for log_file in LOGS.glob("*.log"):
        counts = count_patterns(read_text(log_file))
        for k in log_counts:
            log_counts[k] += counts[k]

    memory = load_memory()
    task_history = memory.get("_taskHistory", [])
    pending_review = memory.get("pending-review", [])

    lines = [
        f"# Daily Summary - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        "## System Health",
        f"- UTC Time: {system_health()['time_utc']}",
        f"- Python: {system_health()['python']}",
        f"- Project Root: {system_health()['cwd']}",
        "",
        "## Agent Activity",
        f"- Task History Entries: {len(task_history)}",
        f"- Pending Review Entries: {len(pending_review)}",
        "",
        "## Errors/Warnings",
        f"- Errors: {log_counts['errors']}",
        f"- Warnings: {log_counts['warnings']}",
        f"- Requests: {log_counts['requests']}",
        "",
        "## Tasks Completed",
    ]

    recent = task_history[-10:]
    if not recent:
        lines.append("- No tasks recorded.")
    else:
        for entry in recent:
            lines.append(f"- {entry.get('timestamp', 'n/a')} :: {entry.get('action', 'unknown')} :: {entry.get('reason', '')}")

    return "\n".join(lines) + "\n"


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out = LOGS / f"daily-summary-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
