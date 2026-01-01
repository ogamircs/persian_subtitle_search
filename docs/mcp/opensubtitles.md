# OpenSubtitles MCP Contract

This adapter expects an MCP server exposing two tools:

1) Search tool (default name: `search_subtitles`)
- Input: { "query": str, "year": int | null, "languages": str, "imdb_id": int | null, ... }
- Output: { "items": [ { "subtitle_id": str, "language": str, "file_name": str | null,
                        "format": str | null, "release": str | null,
                        "download_count": int | null, "score": float | null,
                        "encoding": str | null, "provider_payload": object } ] }

2) Download tool (default name: `download_subtitle`)
- Input: { "subtitle_id": str, ...provider_payload }
- Output: { "content_base64": str, "file_name": str | null, "language": str | null }

## Stdio Mode

Use these env vars to match a stdio MCP server:

- `MCP_OPENSUBTITLES_MODE=stdio`
- `MCP_OPENSUBTITLES_COMMAND=npx`
- `MCP_OPENSUBTITLES_ARGS=-y,@opensubtitles/mcp-server`
- `MCP_OPENSUBTITLES_ENV_MCP_MODE=stdio`
- `MCP_OPENSUBTITLES_ENV_OPENSUBTITLES_USER_KEY=...`

Adjust `MCP_OPENSUBTITLES_CALL_PATH` if your server uses a different HTTP endpoint.
