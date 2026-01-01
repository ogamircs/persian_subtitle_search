from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from src.core.contracts.llm import LLMClient


class OpenAIChatClient(LLMClient):
    def __init__(self, api_key: str, model: str, timeout_s: float = 30.0) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_s)
        self._model = model

    @classmethod
    def from_env(cls) -> Optional["OpenAIChatClient"]:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return cls(api_key=api_key, model=model)

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a precise translation engine."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""
