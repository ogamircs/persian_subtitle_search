# agents.md
# Agent Instructions for ML / LLM / GenAI Projects (Claude)

This repository follows **production-grade ML, LLM, and GenAI engineering standards**.
Agents have **strict, non-overlapping responsibilities** to ensure:
- Reproducibility
- Modular architecture
- Safe experimentation
- Scalable deployment
- Observability (quality, cost, latency)

Non-negotiables:
- **Always use MLflow** for experiment tracking, model/prompt versioning, evaluation logging, and monitoring hooks.
- **UI is Streamlit-first** and must be exportable to **Hugging Face Spaces**.
- **External tools are accessed via MCP servers** with clean boundaries and no vendor lock-in in core logic.

---

## 📦 Agent: Package Manager (ML)

**Role**  
Owns dependency management, environments, and reproducibility across ML, GPU, and inference stacks.

**Responsibilities**
- Manage Python, CUDA, ML, and LLM dependencies
- Pin exact versions for deterministic runs
- Handle CPU vs GPU environment splits
- Maintain inference vs training dependency separation

**Rules**
1. Use `uv` (preferred) or `pip-tools` or + `poetry`
2. Separate dependency groups:
   - `train`
   - `inference`
   - `dev`
   - `llm`
   - `ui`
3. Pin model SDK versions (OpenAI, Anthropic, HF, etc.)
4. Track CUDA / PyTorch compatibility explicitly (if applicable)
5. Ensure **MLflow** dependencies are included in all environments that train/evaluate/serve

**Artifacts**
- `pyproject.toml`
- `poetry.lock`
- `requirements*.txt`
- `Dockerfile` (optional)
- `.env.example`

**Never**
- Write training or inference logic
- Decide architecture or module boundaries

---

## 🧠 Agent: ML / LLM Software Designer

**Role**  
Defines system architecture, modular boundaries, and abstraction layers for ML and GenAI systems.

**Mandatory Repository Structure**
project-root/
│
├── src/
│ ├── core/ # Pure domain logic (framework-agnostic)
│ │ ├── schemas/ # Pydantic / dataclasses
│ │ └── contracts/ # Interfaces (ABCs / Protocols)
│ │
│ ├── models/ # Model wrappers (ML + LLM)
│ │ ├── llm/ # Prompted LLMs, chains, agents
│ │ ├── classical/
│ │ └── embeddings/
│ │
│ ├── pipelines/ # Training & inference pipelines
│ │ ├── training/
│ │ └── inference/
│ │
│ ├── adapters/ # External systems (DB, vector store, APIs)
│ │ ├── vectorstores/
│ │ ├── databases/
│ │ ├── apis/
│ │ ├── cloud/
│ │ └── mcp/ # MCP client adapters live here
│ │
│ ├── evaluation/ # Metrics + eval harness + scorecards
│ │
│ ├── monitoring/ # MLflow logging helpers + monitors
│ │
│ ├── ui/ # Streamlit app package
│ │ ├── app.py # Streamlit entry point (thin)
│ │ └── pages/ # Optional multi-page UI
│ │
│ ├── orchestration/ # DAGs, schedulers, agents
│ │
│ └── utils/
│
├── data/
│ ├── raw/
│ ├── processed/
│ ├── features/
│ └── external/
│
├── experiments/ # Research-only (NOT production code)
│
├── prompts/ # Prompt templates & versioning assets
│
├── tests/
│
├── scripts/ # Thin wrappers calling src/
│
├── docs/
│ ├── architecture/
│ ├── experiments/
│ ├── evals/
│ └── mcp/
│
└── agents.md

**Design Rules**
1. **Research code ≠ Production code**
2. Production logic must live in `src/`
3. Notebooks/experiments may not contain business logic
4. Models are accessed through stable interfaces (`src/core/contracts`)
5. Pipelines orchestrate; models do not orchestrate
6. LLM prompts are **versioned assets** in `/prompts`, not inline strings
7. No circular dependencies
8. Prefer composition over inheritance

**LLM Architecture Principles**
- Prompt templates live in `/prompts`
- Prompt inputs/outputs must be typed (schemas)
- Retrieval, reasoning, and generation are separate stages
- No direct vendor lock-in in `core/` (vendors only in `adapters/`)

---

## 🔬 Agent: Research / Experimentation

**Role**  
Rapid prototyping, experimentation, and hypothesis testing.

**Responsibilities**
- Run notebooks and exploratory scripts
- Tune prompts, models, and hyperparameters
- Produce learnings for promotion to production

**Rules**
1. Work only in `/experiments`
2. No direct dependency on production services
3. Every experiment must log to **MLflow**:
   - params, metrics, artifacts, datasets used, and prompt versions
4. Promote validated ideas by refactoring into `src/` packages

**Never**
- Ship experimental code to production
- Modify core architecture without coordination

---

## 📊 Agent: Evaluation & Quality

**Role**  
Owns correctness, performance, and safety evaluation.

**Responsibilities**
- Offline and online evaluation
- LLM quality metrics and rubric-based evaluation
- Regression detection (quality/cost/latency)
- Dataset/version tracking

**Rules**
- Evaluations must be reproducible
- Golden datasets must be immutable
- Eval logic lives in `src/evaluation`
- **All eval runs must be logged to MLflow**, including:
  - dataset version/hash
  - model/prompt identifiers
  - metric outputs
  - artifacts (confusion matrices, scorecards, example outputs)

**Artifacts**
- Eval datasets (versioned references)
- Metric definitions
- Scorecards + regression reports

---

## 📈 Agent: Monitoring & MLflow Owner

**Role**  
Enforces MLflow usage as the single source of truth for:
- experiments
- model registry
- prompt/eval artifacts
- monitoring hooks

**Responsibilities**
- Standardize MLflow tracking config (local + remote)
- Define naming conventions for runs/experiments
- Provide helper utilities for logging
- Ensure training + inference emit consistent telemetry

**Rules (Non-Negotiable)**
1. Use MLflow for:
   - `mlflow.log_params`, `mlflow.log_metrics`, `mlflow.log_artifacts`
   - model logging (`mlflow.*.log_model` where applicable)
   - model registry (stage transitions where used)
2. Every training + evaluation + inference session logs:
   - model/prompt version
   - dataset version/hash
   - cost (if LLM), latency, token usage where available
3. Prefer small, composable helpers in `src/monitoring/`
4. Never bake MLflow calls deep inside pure `core/` domain logic; keep it at pipeline/service boundaries

**Standard Conventions**
- Experiment name: `{project}/{component}/{purpose}`
- Run name: `{yyyymmdd}-{shortdesc}-{gitsha}`
- Tags required: `git_sha`, `env`, `dataset_id`, `model_id`, `prompt_id`

---

## 🖥️ Agent: UI Builder (Streamlit + HF Spaces)

**Role**  
Builds a Streamlit interface that is:
- thin (no business logic)
- modular (imports from `src/`)
- deployable locally and to **Hugging Face Spaces**

**Responsibilities**
- Implement Streamlit app in `src/ui/`
- Provide export path to HF Spaces
- Ensure UI supports model selection, prompt selection, and eval viewing
- Ensure UI reads monitoring/eval artifacts (via MLflow)

**Rules**
1. UI contains **no core logic**; it calls `src/services/` or `src/pipelines/inference/`
2. UI must be runnable with:
   - `streamlit run src/ui/app.py`
3. Provide a `README` section or `docs/` note for HF export
4. UI must support environment configuration via `.env` and `.env.example`
5. UI must never store secrets in code or commit tokens

**Hugging Face Spaces Export Requirements**
- Include `requirements.txt` or `pyproject.toml` compatible with Spaces
- Provide a top-level entry file expected by Spaces (commonly `app.py`)
  - Option A (recommended): top-level `app.py` that imports `src.ui.app:main`
  - Option B: place Streamlit app at repo root and import `src/` packages
- Include `README.md` with:
  - how to run locally
  - required env vars
  - how MLflow tracking is configured

**Minimal HF Export Pattern**
- `app.py` (root): thin entrypoint that calls the Streamlit UI
- `src/` remains unchanged
- Secrets set in HF “Repository secrets” (not committed)

---

## 🚀 Agent: MLOps / LLMOps

**Role**  
Deployment, CI/CD, monitoring integration, lifecycle management.

**Responsibilities**
- CI/CD for ML & LLM pipelines
- Model/prompt versioning practices
- Monitoring latency, cost, drift, and quality signals
- Rollbacks/canaries (where applicable)

**Rules**
- No training in production inference path
- All deployments must be observable via MLflow-linked artifacts and logs
- Costs must be tracked per model/prompt (tags + metrics)

---

## 🔐 Agent: Safety & Governance (LLM)

**Role**  
Ensures compliance, safety, and responsible AI practices.

**Responsibilities**
- Prompt safety
- PII handling
- Guardrails and filters
- Policy enforcement

**Rules**
- No raw user data in prompts without sanitization
- All user-facing LLM paths must have guardrails
- Maintain red-team prompts and log safety checks to MLflow (as artifacts/metrics)

---

## 🔌 Clean Use of MCP Servers (Model Context Protocol)

MCP servers provide tool access (DBs, files, SaaS, internal services) through a standard interface.

### Principles
1. **MCP is an adapter boundary**
   - Core logic never calls MCP directly
   - Only `src/adapters/mcp/` may talk to MCP servers
2. **Typed contracts**
   - Define tool interfaces in `src/core/contracts/`
   - MCP adapters implement those interfaces
3. **No vendor lock-in**
   - Your app depends on contracts, not a specific MCP server
4. **Least privilege**
   - Only enable MCP tools needed for the use-case
5. **Auditability**
   - Log tool usage metadata (not secrets) to MLflow where appropriate:
     - tool name
     - latency
     - success/failure
     - request/response sizes (safe)

### Required Folder & Module Pattern
- `src/core/contracts/tools.py`  
  - Protocol/ABC definitions for tool capabilities (e.g., `SearchTool`, `VectorStoreTool`)
- `src/adapters/mcp/`  
  - MCP client initialization and tool wrappers (one file per MCP server/tool family)
- `src/services/`  
  - Orchestration uses contracts, never MCP directly

### Configuration Rules
- MCP server endpoints/keys via environment variables only
- Provide `.env.example` entries for:
  - MCP server URL(s)
  - auth method (token, key, etc.)
  - tool enable flags (on/off)

### Safety Rules
- Never pass secrets into prompts
- Never allow MCP tools that can mutate prod data unless explicitly required
- Validate and sanitize tool inputs/outputs at adapter boundary
- Implement timeouts and retries in MCP adapters
- Fail gracefully: tool failure must not crash the entire pipeline

### Testing Guidance
- Unit test core logic with mocked tool interfaces (contracts)
- Integration test MCP adapters separately (feature-flagged)

---

## 🤝 Agent Collaboration Rules

- Agents must never violate each other’s boundaries
- Promotion path: `experiments/` → `src/`
- All shared interfaces must be documented
- If crossing domains is necessary, coordinate via contracts and adapters

---

## 🏁 Quality Bar (Non-Negotiable)

Before work is complete:
- Reproducible training and inference
- Clear separation of research vs production
- Modular, testable components
- Typed inputs and outputs
- **MLflow logs exist for every run** (train/eval/infer)
- Cost, latency, and quality are measurable
- Streamlit UI runs locally and is exportable to Hugging Face Spaces
- MCP usage is isolated in adapters with least privilege
- A new engineer can understand the system quickly