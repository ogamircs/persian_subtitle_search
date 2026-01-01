from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SubtitleSearchQuery(BaseModel):
    movie_name: str = Field(..., min_length=1)
    year: Optional[int] = None
    language: str = Field(..., min_length=2, max_length=8)
    imdb_id: Optional[int] = None


class SubtitleItem(BaseModel):
    subtitle_id: str
    language: str
    file_name: Optional[str] = None
    format: Optional[str] = None
    release: Optional[str] = None
    download_count: Optional[int] = None
    score: Optional[float] = None
    encoding: Optional[str] = None
    provider_payload: Dict[str, Any] = Field(default_factory=dict)


class SubtitleSearchResult(BaseModel):
    items: List[SubtitleItem] = Field(default_factory=list)


class SubtitleDownloadRequest(BaseModel):
    subtitle_id: str
    language: str
    provider_payload: Dict[str, Any] = Field(default_factory=dict)


class SubtitleDownloadResult(BaseModel):
    content_bytes: bytes
    file_name: str
    language: str
    source: str


class SubtitlePipelineResult(BaseModel):
    file_path: str
    language: str
    translated: bool
    content_text: str
    content_bytes: bytes
    selected_item: SubtitleItem
    used_fallback: bool
