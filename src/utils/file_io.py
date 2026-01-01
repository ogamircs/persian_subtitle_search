from __future__ import annotations

import re
from pathlib import Path


def load_prompt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return cleaned.strip("_") or "subtitle"


def write_text_utf8(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
