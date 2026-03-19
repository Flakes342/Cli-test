from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from amex_ai_agent.pipelines.rnn_data_prep.config import RNNDataPrepConfig
from amex_ai_agent.tools.base import ToolExecutionContext


LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2] / "rnn_data_prep"
SPARK_PYTHON_FALLBACK = "/opt/conda/miniconda3/bin/python"


def _report(context: ToolExecutionContext | None, message: str) -> None:
    LOGGER.info(message)
    if context is not None:
        context.report_progress(message)


def _build_config(params: dict[str, Any]) -> RNNDataPrepConfig:
    return RNNDataPrepConfig(
        start_dt=params["start_dt"],
        end_dt=params["end_dt"],
        sample_rate=float(params.get("sample_rate", 0.025)),
        project_id=str(params.get("project_id", "")).strip(),
        dataset_id=str(params.get("dataset_id", "")).strip(),
        folder_nm=str(params.get("folder_nm", "rnn_data_prep")).strip() or "rnn_data_prep",
    )


def _spark_python() -> str:
    return os.getenv("RNN_SPARK_PYTHON") or os.getenv("PYSPARK_PYTHON") or SPARK_PYTHON_FALLBACK


def _apply_spark_env(env: dict[str, str], spark_python: str) -> dict[str, str]:
    env["RNN_SPARK_PYTHON"] = spark_python
    env["PYSPARK_PYTHON"] = spark_python
    env["PYSPARK_DRIVER_PYTHON"] = spark_python
    return env


def _try_import_execution(cfg: RNNDataPrepConfig, context: ToolExecutionContext | None) -> dict[str, Any]:
    if not REPO_ROOT.exists():
        raise FileNotFoundError(f"RNN pipeline folder not found: {REPO_ROOT}")

    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "src"))
    _apply_spark_env(os.environ, _spark_python())
    _report(context, "Loading RNN data prep pipeline...")

    from src.main import run_pipeline  # type: ignore

    pipeline_result = run_pipeline(
        start_dt=cfg.start_dt,
        end_dt=cfg.end_dt,
        sample_rate=cfg.sample_rate,
        project_id=cfg.project_id,
        dataset_id=cfg.dataset_id,
        folder_nm=cfg.folder_nm,
        progress_callback=context.report_progress if context else None,
    )

    return {
        "status": "completed",
        "pipeline": "rnn_data_prep",
        "execution_mode": "python_import",
        "parameters": cfg.to_dict(),
        "result": pipeline_result,
    }


def _try_subprocess_execution(cfg: RNNDataPrepConfig, context: ToolExecutionContext | None) -> dict[str, Any]:
    main_py = REPO_ROOT / "src" / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"Pipeline entrypoint not found: {main_py}")

    spark_python = _spark_python()
    env = _apply_spark_env(os.environ.copy(), spark_python)
    env.update(
        {
            "START_DT": cfg.start_dt,
            "END_DT": cfg.end_dt,
            "SAMPLE_RATE": str(cfg.sample_rate),
            "PROJECT_ID": cfg.project_id,
            "DATASET_ID": cfg.dataset_id,
            "FOLDER_NM": cfg.folder_nm,
        }
    )

    _report(context, "Falling back to subprocess execution...")
    process = subprocess.Popen(
        [spark_python, str(main_py)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        message = line.rstrip()
        if not message:
            continue
        output_lines.append(message)
        _report(context, message)

    process.wait()
    combined_output = "\n".join(output_lines)[-4000:]

    if process.returncode != 0:
        return {
            "status": "failed",
            "pipeline": "rnn_data_prep",
            "execution_mode": "subprocess",
            "parameters": cfg.to_dict(),
            "return_code": process.returncode,
            "stdout": combined_output,
        }

    return {
        "status": "completed",
        "pipeline": "rnn_data_prep",
        "execution_mode": "subprocess",
        "parameters": cfg.to_dict(),
        "stdout": combined_output,
    }


def run_rnn_data_prep(
    params: dict[str, Any],
    context: ToolExecutionContext | None = None,
) -> dict[str, Any]:
    cfg = _build_config(params)

    try:
        return _try_import_execution(cfg, context)
    except Exception as import_exc:  # noqa: BLE001
        LOGGER.info("Import execution unavailable for RNN data prep: %s", import_exc)
        try:
            return _try_subprocess_execution(cfg, context)
        except Exception as subprocess_exc:  # noqa: BLE001
            LOGGER.exception("Subprocess execution failed for RNN data prep.")
            return {
                "status": "failed",
                "pipeline": "rnn_data_prep",
                "parameters": cfg.to_dict(),
                "message": "Failed to execute RNN data prep pipeline.",
                "import_execution_error": str(import_exc),
                "subprocess_execution_error": str(subprocess_exc),
            }
