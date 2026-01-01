from __future__ import annotations

import json
from typing import Dict, Iterable, List

import srt

from src.core.contracts.llm import LLMClient
from src.utils.file_io import load_prompt


class SrtTranslator:
    def __init__(
        self,
        llm: LLMClient,
        prompt_path: str,
        chunk_size: int = 20,
    ) -> None:
        self._llm = llm
        self._prompt_path = prompt_path
        self._chunk_size = chunk_size

    def translate(self, srt_text: str, source_lang: str, target_lang: str) -> str:
        subtitles = list(srt.parse(srt_text))
        if not subtitles:
            return srt_text

        template = load_prompt(self._prompt_path)

        for chunk in self._chunked(subtitles, self._chunk_size):
            items_json = json.dumps(
                [{"id": sub.index, "text": sub.content} for sub in chunk],
                ensure_ascii=False,
            )
            prompt = template.format(
                source_lang=source_lang,
                target_lang=target_lang,
                items_json=items_json,
            )
            response = self._llm.generate(prompt)
            translations = self._parse_json(response)
            if not translations:
                continue

            mapping = {int(item["id"]): item["text"] for item in translations}
            for sub in chunk:
                if sub.index in mapping:
                    sub.content = mapping[sub.index]

        return srt.compose(subtitles)

    @staticmethod
    def _chunked(items: List[srt.Subtitle], size: int) -> Iterable[List[srt.Subtitle]]:
        for i in range(0, len(items), size):
            yield items[i : i + size]

    @staticmethod
    def _parse_json(response: str) -> List[Dict[str, str]]:
        start = response.find("[")
        end = response.rfind("]")
        if start == -1 or end == -1:
            return []
        try:
            data = json.loads(response[start : end + 1])
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict) and "id" in item]
