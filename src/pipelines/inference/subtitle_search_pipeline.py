from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, List, Optional

from src.core.contracts.tools import SubtitleSearchTool
from src.core.schemas.subtitles import (
    SubtitleDownloadRequest,
    SubtitleItem,
    SubtitlePipelineResult,
    SubtitleSearchQuery,
)
from src.models.llm.srt_translator import ProgressCallback, SrtTranslator
from src.monitoring.mlflow_utils import MLflowLogger
from src.utils.encoding import decode_bytes
from src.utils.file_io import safe_filename, write_text_utf8


class SubtitleSearchPipeline:
    def __init__(
        self,
        tool: SubtitleSearchTool,
        translator: Optional[SrtTranslator],
        logger: MLflowLogger,
        storage_dir: Path,
    ) -> None:
        self._tool = tool
        self._translator = translator
        self._logger = logger
        self._storage_dir = storage_dir

    def search(self, movie_name: str, year: Optional[int], language: str) -> List[SubtitleItem]:
        query = SubtitleSearchQuery(
            movie_name=movie_name,
            year=year,
            language=language,
        )
        start = time.perf_counter()
        result = self._tool.search(query)
        latency_ms = (time.perf_counter() - start) * 1000
        self._logger.log_metric("search_latency_ms", latency_ms)
        self._logger.log_metric("search_count", len(result.items))
        return result.items

    @staticmethod
    def _select_best(items: List[SubtitleItem]) -> Optional[SubtitleItem]:
        if not items:
            return None
        return sorted(
            items,
            key=lambda item: (
                item.score or 0.0,
                item.download_count or 0,
            ),
            reverse=True,
        )[0]

    def download_item(self, item: SubtitleItem) -> str:
        request = SubtitleDownloadRequest(
            subtitle_id=item.subtitle_id,
            language=item.language,
            provider_payload=item.provider_payload,
        )
        start = time.perf_counter()
        result = self._tool.download(request)
        latency_ms = (time.perf_counter() - start) * 1000
        self._logger.log_metric("download_latency_ms", latency_ms)
        return decode_bytes(result.content_bytes)

    def _finalize_download(
        self,
        movie_name: str,
        item: SubtitleItem,
        content_text: str,
        target_lang: str,
        translated: bool,
        used_fallback: bool,
    ) -> SubtitlePipelineResult:
        file_name = safe_filename(item.file_name or movie_name)
        output_path = self._storage_dir / f"{file_name}.{target_lang}.srt"
        write_text_utf8(output_path, content_text)
        self._logger.log_artifact(output_path)

        return SubtitlePipelineResult(
            file_path=str(output_path),
            language=target_lang if translated else item.language,
            translated=translated,
            content_text=content_text,
            content_bytes=content_text.encode("utf-8"),
            selected_item=item,
            used_fallback=used_fallback,
        )

    def run(
        self,
        movie_name: str,
        year: Optional[int],
        prefer_lang: str = "fa",
        fallback_lang: str = "en",
    ) -> SubtitlePipelineResult:
        run_name = f"subtitle-search-{safe_filename(movie_name)}"
        with self._logger.start_run(run_name=run_name):
            self._logger.log_params(
                {
                    "movie_name": movie_name,
                    "year": year or "",
                    "prefer_lang": prefer_lang,
                    "fallback_lang": fallback_lang,
                }
            )

            items = self.search(movie_name, year, prefer_lang)
            used_fallback = False
            if not items:
                items = self.search(movie_name, year, fallback_lang)
                used_fallback = True

            best = self._select_best(items)
            if not best:
                raise ValueError("No subtitles found")

            content_text = self.download_item(best)
            translated = False
            if best.language != prefer_lang:
                if not self._translator:
                    raise ValueError("No translator configured for fallback translation")
                content_text = self._translator.translate(
                    content_text,
                    source_lang=best.language,
                    target_lang=prefer_lang,
                )
                translated = True

            return self._finalize_download(
                movie_name=movie_name,
                item=best,
                content_text=content_text,
                target_lang=prefer_lang,
                translated=translated,
                used_fallback=used_fallback,
            )

    def download_selected(
        self,
        movie_name: str,
        item: SubtitleItem,
        target_lang: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> SubtitlePipelineResult:
        run_name = f"subtitle-download-{safe_filename(movie_name)}"
        with self._logger.start_run(run_name=run_name):
            self._logger.log_params(
                {
                    "movie_name": movie_name,
                    "selected_language": item.language,
                    "target_lang": target_lang,
                }
            )

            content_text = self.download_item(item)
            translated = False
            if item.language != target_lang:
                if not self._translator:
                    raise ValueError("No translator configured for fallback translation")
                content_text = self._translator.translate(
                    content_text,
                    source_lang=item.language,
                    target_lang=target_lang,
                    progress_callback=progress_callback,
                )
                translated = True

            return self._finalize_download(
                movie_name=movie_name,
                item=item,
                content_text=content_text,
                target_lang=target_lang,
                translated=translated,
                used_fallback=False,
            )
