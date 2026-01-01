from __future__ import annotations

import chardet


def decode_bytes(data: bytes) -> str:
    if not data:
        return ""
    detected = chardet.detect(data)
    encoding = detected.get("encoding") or "utf-8"
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")
