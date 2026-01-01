from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator

import mlflow

from src.utils.git import get_git_sha


class MLflowLogger:
    def __init__(self, tracking_uri: str, experiment_name: str, env: str) -> None:
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name
        self._env = env
        if self._tracking_uri:
            mlflow.set_tracking_uri(self._tracking_uri)

    @classmethod
    def from_env(cls) -> "MLflowLogger":
        return cls(
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", ""),
            experiment_name=os.getenv(
                "MLFLOW_EXPERIMENT_NAME", "persian_subtitle_search/inference/search"
            ),
            env=os.getenv("ENV", "local"),
        )

    @contextmanager
    def start_run(self, run_name: str) -> Iterator[None]:
        mlflow.set_experiment(self._experiment_name)
        # End any active run before starting a new one
        if mlflow.active_run():
            mlflow.end_run()
        with mlflow.start_run(run_name=run_name):
            mlflow.set_tags(
                {
                    "git_sha": get_git_sha(),
                    "env": self._env,
                    "dataset_id": "n/a",
                    "model_id": os.getenv("OPENAI_MODEL", "n/a"),
                    "prompt_id": os.getenv("PROMPT_TRANSLATE_SRT", "n/a"),
                }
            )
            yield

    def log_params(self, params: Dict[str, object]) -> None:
        if mlflow.active_run():
            mlflow.log_params(params)

    def log_metric(self, key: str, value: float) -> None:
        if mlflow.active_run():
            mlflow.log_metric(key, value)

    def log_tool_call(
        self,
        tool_name: str,
        latency_ms: float,
        success: bool,
        request_bytes: int,
        response_bytes: int,
    ) -> None:
        if mlflow.active_run():
            mlflow.log_metric(f"tool_{tool_name}_latency_ms", latency_ms)
            mlflow.log_metric(f"tool_{tool_name}_request_bytes", request_bytes)
            mlflow.log_metric(f"tool_{tool_name}_response_bytes", response_bytes)
            mlflow.log_metric(f"tool_{tool_name}_success", 1 if success else 0)

    def log_artifact(self, path: Path) -> None:
        if mlflow.active_run():
            mlflow.log_artifact(str(path))
