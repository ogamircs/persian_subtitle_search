# Persian Subtitle Search

Search, download, and translate subtitles via an OpenSubtitles MCP server with a Streamlit UI.

## Requirements

- Python >= 3.10
- Node.js (for the MCP server via `npx`)
- OpenSubtitles API key (free at https://www.opensubtitles.com/en/consumers)
- OpenAI API key (optional, for translation)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/persian-subtitle-search.git
cd persian-subtitle-search
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -e ".[ui,llm]"
```

4. Copy `.env.example` to `.env` and configure your API keys:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Running the App

```bash
streamlit run src/ui/app.py
```

The app will be available at http://localhost:8501

## Features

- Search for subtitles by movie name and year
- Filter by language (Persian/English)
- Automatic fallback to English if Persian subtitles are unavailable
- Optional translation of non-Persian subtitles to Persian using OpenAI

## Configuration

### MCP Server (OpenSubtitles)
The app uses an MCP (Model Context Protocol) server to communicate with OpenSubtitles. Set these in `.env`:
- `MCP_OPENSUBTITLES_MODE=stdio`
- `MCP_OPENSUBTITLES_COMMAND=npx`
- `MCP_OPENSUBTITLES_ARGS=-y,@opensubtitles/mcp-server`
- `MCP_OPENSUBTITLES_ENV_OPENSUBTITLES_USER_KEY=your_key_here`

### Translation
To enable automatic translation of English subtitles to Persian:
- Set `TRANSLATION_PROVIDER=openai`
- Set `OPENAI_API_KEY=your_openai_key_here`
- Set `OPENAI_MODEL=gpt-4o-mini` (or another model)

### MLflow (Optional)
For experiment tracking, set `MLFLOW_TRACKING_URI` to your MLflow server URL. Leave empty for local tracking.

## Project Structure

```
persian_subtitle_search/
├── app.py                 # Root entrypoint (for HF Spaces)
├── src/
│   ├── adapters/          # External service adapters (MCP, OpenAI)
│   ├── core/              # Domain schemas and contracts
│   ├── models/            # LLM wrappers (translator)
│   ├── monitoring/        # MLflow logging
│   ├── pipelines/         # Orchestration logic
│   ├── services/          # Service layer
│   ├── ui/                # Streamlit app
│   └── utils/             # Helper functions
├── prompts/               # LLM prompt templates
└── docs/                  # Documentation
```

## License

MIT
