from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .constants import FLAG_REGEX

RESULT_FIELDNAMES = [
    "run_id",
    "timestamp_utc",
    "backend",
    "model_alias",
    "model_name",
    "prompt_id",
    "category",
    "temperature",
    "secret_sha256",
    "status",
    "breach",
    "detected_secret",
    "latency_ms",
    "response_text",
    "error_message",
]


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_breach(response_text: str) -> tuple[bool, str]:
    match = FLAG_REGEX.search(response_text or "")
    if not match:
        return False, ""
    return True, match.group(0)


def load_existing_result_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            (row["model_alias"], row["prompt_id"])
            for row in reader
            if row.get("model_alias") and row.get("prompt_id")
        }


def append_result(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
