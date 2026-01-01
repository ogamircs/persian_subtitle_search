from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from src.adapters.apis.openai_translator import OpenAIChatClient
from src.adapters.mcp.opensubtitles_client import OpenSubtitlesMCPAdapter
from src.adapters.mcp.opensubtitles_stdio import OpenSubtitlesMCPStdioAdapter
from src.core.schemas.subtitles import SubtitleItem, SubtitlePipelineResult
from src.models.llm.srt_translator import SrtTranslator
from src.monitoring.mlflow_utils import MLflowLogger
from src.pipelines.inference.subtitle_search_pipeline import SubtitleSearchPipeline


class SubtitleService:
    def __init__(self, pipeline: SubtitleSearchPipeline) -> None:
        self._pipeline = pipeline

    def search(self, movie_name: str, year: Optional[int], language: str) -> List[SubtitleItem]:
        return self._pipeline.search(movie_name, year, language)

    def download_best(
        self,
        movie_name: str,
        year: Optional[int],
        prefer_lang: str = "fa",
    ) -> SubtitlePipelineResult:
        return self._pipeline.run(movie_name, year, prefer_lang=prefer_lang)

    def download_selected(
        self,
        movie_name: str,
        item: SubtitleItem,
        target_lang: str,
    ) -> SubtitlePipelineResult:
        return self._pipeline.download_selected(movie_name, item, target_lang)


def build_service_from_env() -> SubtitleService:
    logger = MLflowLogger.from_env()
    mode = os.getenv("MCP_OPENSUBTITLES_MODE", "http").strip().lower()
    if mode == "stdio":
        tool = OpenSubtitlesMCPStdioAdapter.from_env(logger=logger)
    else:
        tool = OpenSubtitlesMCPAdapter.from_env(logger=logger)
    provider = os.getenv("TRANSLATION_PROVIDER", "openai").strip().lower()
    llm_client = OpenAIChatClient.from_env() if provider == "openai" else None
    prompt_path = os.getenv("PROMPT_TRANSLATE_SRT", "prompts/translate_srt.txt")
    translator = SrtTranslator(llm_client, prompt_path) if llm_client else None
    storage_dir = Path(os.getenv("SUBTITLE_STORAGE_DIR", "data/processed/subtitles"))
    pipeline = SubtitleSearchPipeline(tool, translator, logger, storage_dir)
    return SubtitleService(pipeline)
