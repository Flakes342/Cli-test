from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import replace

from amex_ai_agent.config import AgentConfig, ConfigLoader


class StartupManager:
    """Interactive runtime bootstrap for restricted environments."""

    def __init__(self, loader: ConfigLoader) -> None:
        self.loader = loader

    def initialize(self, config: AgentConfig, *, prompt_for_auth: bool) -> AgentConfig:
        resolved = replace(config)

        if not resolved.default_project_id:
            resolved.default_project_id = self._prompt("Default BigQuery project_id")
        if not resolved.default_dataset_id:
            resolved.default_dataset_id = self._prompt("Default BigQuery dataset_id")

        resolved.default_folder_nm = self._prompt(
            "Default folder name",
            default=resolved.default_folder_nm,
            required=False,
        ) or resolved.default_folder_nm
        resolved.spark_python = self._prompt(
            "Spark Python path",
            default=resolved.spark_python,
            required=False,
        ) or resolved.spark_python

        os.environ["RNN_SPARK_PYTHON"] = resolved.spark_python
        self.loader.save(resolved)

        if prompt_for_auth:
            self._maybe_run_gcloud_auth()

        return resolved

    def _maybe_run_gcloud_auth(self) -> None:
        if shutil.which("gcloud") is None:
            return

        answer = self._prompt(
            "Run `gcloud auth login` now? [y/N]",
            default="n",
            required=False,
        ).strip().lower()
        if answer not in {"y", "yes"}:
            return

        subprocess.run(["gcloud", "auth", "login"], check=False)

    def _prompt(self, label: str, default: str = "", required: bool = True) -> str:
        while True:
            suffix = f" [{default}]" if default else ""
            value = input(f"{label}{suffix}: ").strip()
            if value:
                return value
            if default:
                return default
            if not required:
                return ""
            print(f"{label} is required.")
