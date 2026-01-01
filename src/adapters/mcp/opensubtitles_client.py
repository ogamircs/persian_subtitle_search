from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, Optional

import httpx

from src.core.contracts.tools import SubtitleSearchTool
from src.core.schemas.subtitles import (
    SubtitleDownloadRequest,
    SubtitleDownloadResult,
    SubtitleItem,
    SubtitleSearchQuery,
    SubtitleSearchResult,
)
from src.monitoring.mlflow_utils import MLflowLogger


class OpenSubtitlesMCPAdapter(SubtitleSearchTool):
    def __init__(
        self,
        base_url: str,
        call_path: str,
        tool_search: str,
        tool_download: str,
        auth_token: Optional[str] = None,
        timeout_s: float = 30.0,
        logger: Optional[MLflowLogger] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._call_path = call_path
        self._tool_search = tool_search
        self._tool_download = tool_download
        self._auth_token = auth_token
        self._timeout_s = timeout_s
        self._logger = logger

    @classmethod
    def from_env(cls, logger: Optional[MLflowLogger] = None) -> "OpenSubtitlesMCPAdapter":
        return cls(
            base_url=os.getenv("MCP_OPENSUBTITLES_URL", "").strip(),
            call_path=os.getenv("MCP_OPENSUBTITLES_CALL_PATH", "/tools/call").strip(),
            tool_search=os.getenv("MCP_OPENSUBTITLES_TOOL_SEARCH", "search_subtitles").strip(),
            tool_download=os.getenv("MCP_OPENSUBTITLES_TOOL_DOWNLOAD", "download_subtitle").strip(),
            auth_token=os.getenv("MCP_OPENSUBTITLES_AUTH_TOKEN", "").strip() or None,
            timeout_s=float(os.getenv("MCP_OPENSUBTITLES_TIMEOUT_S", "30")),
            logger=logger,
        )

    def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self._base_url:
            raise ValueError("MCP_OPENSUBTITLES_URL is not set")

        url = f"{self._base_url}{self._call_path}"
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        payload = {"name": tool_name, "arguments": arguments}
        start = time.perf_counter()
        success = False
        response_bytes = 0

        with httpx.Client(timeout=self._timeout_s) as client:
            response = client.post(url, json=payload, headers=headers)
            response_bytes = len(response.content or b"")
            response.raise_for_status()
            data = response.json()

        success = True
        latency_ms = (time.perf_counter() - start) * 1000
        if self._logger:
            self._logger.log_tool_call(
                tool_name=tool_name,
                latency_ms=latency_ms,
                success=success,
                request_bytes=len(str(payload).encode("utf-8")),
                response_bytes=response_bytes,
            )

        return data.get("result", data)

    def search(self, query: SubtitleSearchQuery) -> SubtitleSearchResult:
        raw = self._call_tool(
            self._tool_search,
            {
                "query": query.movie_name,
                "year": query.year,
                "languages": query.language,
                "imdb_id": query.imdb_id,
            },
        )
        items = []
        for entry in raw.get("items", raw.get("data", [])):
            items.append(
                SubtitleItem(
                    subtitle_id=str(entry.get("subtitle_id") or entry.get("id") or ""),
                    language=str(entry.get("language") or query.language),
                    file_name=entry.get("file_name"),
                    format=entry.get("format"),
                    release=entry.get("release"),
                    download_count=entry.get("download_count"),
                    score=entry.get("score"),
                    encoding=entry.get("encoding"),
                    provider_payload=entry.get("provider_payload", {}),
                )
            )
        return SubtitleSearchResult(items=items)

    def download(self, request: SubtitleDownloadRequest) -> SubtitleDownloadResult:
        raw = self._call_tool(
            self._tool_download,
            {"subtitle_id": request.subtitle_id, **request.provider_payload},
        )
        content_b64 = raw.get("content_base64") or raw.get("content_b64")
        if content_b64:
            content_bytes = base64.b64decode(content_b64)
        else:
            content_text = raw.get("content", "")
            content_bytes = content_text.encode("utf-8", errors="replace")

        file_name = raw.get("file_name") or f"{request.subtitle_id}.srt"
        language = raw.get("language") or request.language

        return SubtitleDownloadResult(
            content_bytes=content_bytes,
            file_name=file_name,
            language=language,
            source="opensubtitles_mcp",
        )
