"""Test script to debug MCP search issues."""
from src.adapters.mcp.opensubtitles_stdio import OpenSubtitlesMCPStdioAdapter
from src.core.schemas.subtitles import SubtitleSearchQuery
from dotenv import load_dotenv

load_dotenv()

adapter = OpenSubtitlesMCPStdioAdapter.from_env()

print("=" * 50)
print("Testing Persian search...")
print("=" * 50)
try:
    result = adapter.search(SubtitleSearchQuery(movie_name="Sentimental Value", language="fa"))
    print(f"Persian results: {len(result.items)} items")
    for item in result.items[:3]:
        print(f"  - {item.language}: {item.release or item.file_name}")
except Exception as e:
    print(f"Persian search error: {e}")

print()
print("=" * 50)
print("Testing English search...")
print("=" * 50)
try:
    result = adapter.search(SubtitleSearchQuery(movie_name="Sentimental Value", language="en"))
    print(f"English results: {len(result.items)} items")
    for item in result.items[:3]:
        print(f"  - {item.language}: {item.release or item.file_name}")
except Exception as e:
    print(f"English search error: {e}")

print()
print("Done!")
