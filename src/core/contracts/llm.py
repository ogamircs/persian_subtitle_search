from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...
