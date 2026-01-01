from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

from src.core.contracts.tools import SubtitleSearchTool
from src.core.schemas.subtitles import (
    SubtitleDownloadRequest,
    SubtitleDownloadResult,
    SubtitleItem,
    SubtitleSearchQuery,
    SubtitleSearchResult,
)
from src.monitoring.mlflow_utils import MLflowLogger


class OpenSubtitlesMCPStdioAdapter(SubtitleSearchTool):
    def __init__(
        self,
        command: str,
        args: list[str],
        env: Dict[str, str],
        tool_search: str,
        tool_download: str,
        timeout_s: float = 30.0,
        logger: Optional[MLflowLogger] = None,
    ) -> None:
        self._command = command
        self._args = args
        self._env = env
        self._tool_search = tool_search
        self._tool_download = tool_download
        self._timeout_s = timeout_s
        self._logger = logger

    @classmethod
    def from_env(cls, logger: Optional[MLflowLogger] = None) -> "OpenSubtitlesMCPStdioAdapter":
        command = os.getenv("MCP_OPENSUBTITLES_COMMAND", "npx").strip()
        args_raw = os.getenv("MCP_OPENSUBTITLES_ARGS", "-y,@opensubtitles/mcp-server")
        args = [part.strip() for part in args_raw.split(",") if part.strip()]
        env = _load_prefixed_env("MCP_OPENSUBTITLES_ENV_")
        return cls(
            command=command,
            args=args,
            env=env,
            tool_search=os.getenv("MCP_OPENSUBTITLES_TOOL_SEARCH", "search_subtitles").strip(),
            tool_download=os.getenv("MCP_OPENSUBTITLES_TOOL_DOWNLOAD", "download_subtitle").strip(),
            timeout_s=float(os.getenv("MCP_OPENSUBTITLES_TIMEOUT_S", "10")),
            logger=logger,
        )

    def search(self, query: SubtitleSearchQuery) -> SubtitleSearchResult:
        arguments: Dict[str, Any] = {
            "query": query.movie_name,
            "languages": query.language,
        }
        if query.year is not None:
            arguments["year"] = query.year
        if query.imdb_id is not None:
            arguments["imdb_id"] = query.imdb_id
        result = self._run_tool(self._tool_search, arguments)
        items = []
        # Handle different response formats from MCP server
        subtitles = result.get("subtitles", result.get("items", result.get("data", [])))
        for entry in subtitles:
            # Extract nested fields
            quality_info = entry.get("quality_info", {})
            upload_info = entry.get("upload_info", {})
            files = entry.get("files", [])
            file_name = files[0].get("file_name") if files else entry.get("file_name")
            file_id = files[0].get("file_id") if files else None

            items.append(
                SubtitleItem(
                    subtitle_id=str(entry.get("subtitle_id") or entry.get("id") or ""),
                    language=str(entry.get("language") or query.language),
                    file_name=file_name,
                    format=entry.get("format"),
                    release=upload_info.get("release") or entry.get("release"),
                    download_count=quality_info.get("download_count") or entry.get("download_count"),
                    score=entry.get("score"),
                    encoding=entry.get("encoding"),
                    provider_payload={"file_id": file_id} if file_id else entry.get("provider_payload", {}),
                )
            )
        return SubtitleSearchResult(items=items)

    def download(self, request: SubtitleDownloadRequest) -> SubtitleDownloadResult:
        result = self._run_tool(
            self._tool_download,
            {"subtitle_id": request.subtitle_id, **request.provider_payload},
        )
        content_b64 = result.get("content_base64") or result.get("content_b64")
        if content_b64:
            content_bytes = _decode_base64(content_b64)
        else:
            content_text = result.get("content", "")
            content_bytes = content_text.encode("utf-8", errors="replace")

        file_name = result.get("file_name") or f"{request.subtitle_id}.srt"
        language = result.get("language") or request.language

        return SubtitleDownloadResult(
            content_bytes=content_bytes,
            file_name=file_name,
            language=language,
            source="opensubtitles_mcp_stdio",
        )

    def _run_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self._command:
            raise ValueError("MCP_OPENSUBTITLES_COMMAND is not set")

        import threading
        import time

        # Build all requests to send at once
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "python-client", "version": "1.0.0"}
            }
        }
        init_notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }

        # Combine all requests into single input
        input_data = "\n".join([
            json.dumps(init_request),
            json.dumps(init_notification),
            json.dumps(tool_request),
        ]) + "\n"

        # Merge environment
        merged_env = {**os.environ, **self._env}

        # Run subprocess with Popen
        cmd = [self._command] + self._args

        print(f"[DEBUG] Starting subprocess for {tool_name}", flush=True)

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
        )

        print(f"[DEBUG] Subprocess started, PID={process.pid}", flush=True)

        # Write input and close stdin to signal we're done sending
        process.stdin.write(input_data.encode("utf-8"))
        process.stdin.flush()
        process.stdin.close()

        # Read stdout lines in a separate thread with timeout
        result = None
        lines_read = []

        def read_output():
            nonlocal result, lines_read
            try:
                for line in process.stdout:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    lines_read.append(line_str)
                    print(f"[DEBUG] Received line: {line_str[:200]}...", flush=True)
                    try:
                        response = json.loads(line_str)
                        if response.get("id") == 2:
                            result = response
                            return  # Got what we need
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                print(f"[DEBUG] Read error: {e}", flush=True)

        reader_thread = threading.Thread(target=read_output, daemon=True)
        reader_thread.start()
        reader_thread.join(timeout=self._timeout_s)

        # Kill the process regardless (MCP server stays alive otherwise)
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True
                )
            else:
                process.kill()
            process.wait(timeout=5)
        except Exception:
            pass

        print(f"[DEBUG] Read {len(lines_read)} lines, result found: {result is not None}", flush=True)

        if result and "result" in result:
            return _extract_tool_result_from_jsonrpc(result["result"])
        elif result and "error" in result:
            raise RuntimeError(f"MCP error: {result['error']}")
        else:
            # Return empty on timeout/no result
            return {"subtitles": []}


def _decode_base64(value: str) -> bytes:
    import base64

    return base64.b64decode(value)


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from text, handling markdown code blocks."""
    import re

    # First try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    json_match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _extract_tool_result_from_jsonrpc(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tool result from JSON-RPC response."""
    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    extracted = _extract_json_from_text(text)
                    if extracted:
                        return extracted
    return {}


def _load_prefixed_env(prefix: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            target_key = key[len(prefix) :]
            if target_key:
                values[target_key] = value
    return values
