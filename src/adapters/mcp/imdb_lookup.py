"""IMDB lookup adapter using RapidAPI MCP server."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class IMDBResult:
    """Result from IMDB lookup."""
    imdb_id: str  # e.g., "tt5014882"
    title: str
    type: str  # movie, tvSeries, tvMovie, etc.
    year: Optional[int] = None
    description: Optional[str] = None


class IMDBLookupAdapter:
    """Adapter for looking up IMDB IDs via RapidAPI MCP server."""

    def __init__(
        self,
        command: str,
        args: list[str],
        timeout_s: float = 30.0,
    ) -> None:
        self._command = command
        self._args = args
        self._timeout_s = timeout_s

    @classmethod
    def from_env(cls) -> "IMDBLookupAdapter":
        """Create adapter from environment variables."""
        command = os.getenv("IMDB_MCP_COMMAND", "npx").strip()
        args_raw = os.getenv(
            "IMDB_MCP_ARGS",
            "mcp-remote,https://mcp.rapidapi.com,--header,x-api-host: imdb236.p.rapidapi.com,--header,x-api-key: 7b5f9ce880msh7a2f8a24e98b902p1d4789jsn31b1fd745791"
        )
        args = [part.strip() for part in args_raw.split(",") if part.strip()]
        return cls(
            command=command,
            args=args,
            timeout_s=float(os.getenv("IMDB_MCP_TIMEOUT_S", "30")),
        )

    def lookup(self, query: str) -> List[IMDBResult]:
        """Look up IMDB ID by title search."""
        result = self._run_tool("Autocomplete", {"query": query})

        items = []
        if isinstance(result, list):
            for entry in result:
                imdb_id = entry.get("id", "")
                if imdb_id:
                    items.append(IMDBResult(
                        imdb_id=imdb_id,
                        title=entry.get("primaryTitle", ""),
                        type=entry.get("type", ""),
                        year=entry.get("startYear"),
                        description=entry.get("description"),
                    ))
        return items

    def lookup_best_match(
        self, query: str, year: Optional[int] = None, type_hint: Optional[str] = None
    ) -> Optional[IMDBResult]:
        """Look up and return best matching result."""
        results = self.lookup(query)
        if not results:
            return None

        # Score results based on match criteria
        def score(r: IMDBResult) -> int:
            s = 0
            # Exact title match (case insensitive)
            if r.title.lower() == query.lower():
                s += 100
            elif query.lower() in r.title.lower():
                s += 50
            # Year match
            if year and r.year == year:
                s += 30
            # Type match
            if type_hint:
                type_map = {"tvshow": "tvSeries", "movie": "movie", "episode": "tvEpisode"}
                expected_type = type_map.get(type_hint, type_hint)
                if r.type == expected_type:
                    s += 20
            return s

        results_scored = sorted(results, key=score, reverse=True)
        return results_scored[0] if results_scored else None

    def _run_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Run MCP tool and return result."""
        import time

        if not self._command:
            raise ValueError("IMDB_MCP_COMMAND is not set")

        # Build JSON-RPC requests
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

        cmd = [self._command] + self._args

        print(f"[DEBUG IMDB] Starting subprocess for {tool_name}", flush=True)

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Read output with timeout in a thread
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
                    print(f"[DEBUG IMDB] Received: {line_str[:100]}...", flush=True)
                    try:
                        response = json.loads(line_str)
                        if response.get("id") == 2:
                            result = response
                            return
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                print(f"[DEBUG IMDB] Read error: {e}", flush=True)

        reader_thread = threading.Thread(target=read_output, daemon=True)
        reader_thread.start()

        # Send messages with delays (mcp-remote needs time to connect)
        time.sleep(2)  # Wait for connection
        process.stdin.write((json.dumps(init_request) + "\n").encode("utf-8"))
        process.stdin.flush()
        time.sleep(1)
        process.stdin.write((json.dumps(init_notification) + "\n").encode("utf-8"))
        process.stdin.flush()
        time.sleep(0.5)
        process.stdin.write((json.dumps(tool_request) + "\n").encode("utf-8"))
        process.stdin.flush()

        # Wait for response
        reader_thread.join(timeout=self._timeout_s - 4)

        # Kill process
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

        print(f"[DEBUG IMDB] Read {len(lines_read)} lines, result found: {result is not None}", flush=True)

        if result and "result" in result:
            return self._extract_tool_result(result["result"])
        elif result and "error" in result:
            raise RuntimeError(f"IMDB MCP error: {result['error']}")

        return []

    def _extract_tool_result(self, result: Dict[str, Any]) -> Any:
        """Extract tool result from JSON-RPC response."""
        content = result.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            pass
        return []
