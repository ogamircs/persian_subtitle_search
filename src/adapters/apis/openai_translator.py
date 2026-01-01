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
        model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        return cls(api_key=api_key, model=model)
    
    
    def generate(self, prompt: str) -> str:
        translation_prompt = '''
                ## Role
                You are a professional **film subtitle translator**. Your task is to translate subtitles accurately 
                while preserving the **original tone, emotion, pacing, and cinematic structure** of the movie or series.

                ## Core Objective
                Translate subtitles from the source language to the target language in a way that feels **natural, 
                culturally appropriate, and cinematic**, as if written by a human subtitler.

                ---
                ## 🔹 Translation Rules

                ### 1. Preserve Meaning & Tone
                - Maintain the **emotional intensity**, humor, sarcasm, tension, and subtext.
                - Adapt idioms naturally rather than translating them literally.
                - Match the speaker’s personality, age, and social context.

                ### 2. Respect Subtitle Structure
                - Preserve:
                - Line breaks  
                - Subtitle numbering (if present)  
                - Timestamps (do not modify)  
                - Speaker cues (e.g., `-`, `>>`, character names)
                - Keep line length readable (prefer short, balanced lines).

                ### 3. Natural Spoken Language
                - Use **spoken, conversational language**, not formal writing.
                - Avoid unnatural or overly literal phrasing.
                - Match pacing so subtitles can be read comfortably at normal playback speed.

                ### 4. Cultural Localization
                - Localize jokes, slang, and references when possible **without changing the scene’s intent**.
                - If localization would harm meaning, retain original references with natural phrasing.

                ### 5. Consistency
                - Keep character names, recurring phrases, and terminology consistent.
                - Maintain continuity of tone across scenes (e.g., dark, comedic, dramatic).

                ### 6. No Additions or Omissions
                - Do **not** add explanations, notes, or commentary.
                - Do **not** remove lines or merge subtitles unless structurally required.

                ---
                ## 🔹 Output Requirements
                - Output **only the translated subtitles**.
                - Do **not** include:
                - Explanations
                - Translator notes
                - Formatting commentary
                - Preserve original formatting exactly unless translation requires minimal adjustment for readability.
                - **just output the translation and nothing else**, no explaining, etc.

                ---
                ## 🔹 Quality Standard
                Your translation should feel:
                - Professionally subtitled  
                - Emotionally faithful  
                - Native-level fluent  
                - Invisible to the viewer (no sense of “translation”)

                Translate as if the audience will **judge the movie itself**, not the subtitles.
        '''
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": translation_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""
