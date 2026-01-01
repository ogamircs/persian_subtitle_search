from __future__ import annotations

from typing import Protocol

from src.core.schemas.subtitles import (
    SubtitleDownloadRequest,
    SubtitleDownloadResult,
    SubtitleSearchQuery,
    SubtitleSearchResult,
)


class SubtitleSearchTool(Protocol):
    def search(self, query: SubtitleSearchQuery) -> SubtitleSearchResult:
        ...

    def download(self, request: SubtitleDownloadRequest) -> SubtitleDownloadResult:
        ...
