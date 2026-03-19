# from _future_ import annotations

# import os
# import subprocess
# import sys
# import traceback
# from pathlib import Path
# from typing import Any, Dict

# from pipelines.rnn_data_prep.config import RNNDataPrepConfig

# # Change this to wherever your extracted repo lives in your agent project
# REPO_ROOT = Path(_file_).resolve().parents[2] / "rnn_data_prep"

from _future_ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from pipelines.rnn_data_prep.config import RNNDataPrepConfig

REPO_ROOT = Path(_file_).resolve().parents[2] / "rnn_data_prep"
SPARK_PYTHON = os.getenv("RNN_SPARK_PYTHON", "/opt/conda/miniconda3/bin/python")



def _build_config(params: Dict[str, Any]) -> RNNDataPrepConfig:
    return RNNDataPrepConfig(
        start_dt=params["start_dt"],
        end_dt=params["end_dt"],
        sample_rate=float(params.get("sample_rate", 0.025)),
        project_id=params.get("project_id", "prj-p-ai-fraud"),
        dataset_id=params.get("dataset_id", "atanw9"),
        folder_nm=params.get("folder_nm", "rnn_test"),
    )


def _try_import_execution(cfg: RNNDataPrepConfig) -> Dict[str, Any]:
    """
    Preferred path if you refactor the existing repo to expose a callable:
        from src.main import run_pipeline
    """

    repo_src = REPO_ROOT / "src"

    import sys
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(repo_src))

    from src.main import run_pipeline
    if not repo_src.exists():
        raise FileNotFoundError(f"Repo src directory not found: {repo_src}")

    sys.path.insert(0, str(REPO_ROOT))

    try:
        # You should add this function to your repo's src/main.py
        from src.main import run_pipeline  # type: ignore
    except Exception as exc:
        raise ImportError(
            "Could not import run_pipeline from src.main. "
            "Refactor your existing repo to expose run_pipeline(...)."
        ) from exc

    pipeline_result = run_pipeline(
        start_dt=cfg.start_dt,
        end_dt=cfg.end_dt,
        sample_rate=cfg.sample_rate,
        project_id=cfg.project_id,
        dataset_id=cfg.dataset_id,
        folder_nm=cfg.folder_nm,
    )

    return {
        "status": "completed",
        "pipeline": "rnn_data_prep",
        "execution_mode": "python_import",
        "parameters": cfg._dict_,
        "result": pipeline_result,
    }


def _try_subprocess_execution(cfg: RNNDataPrepConfig) -> Dict[str, Any]:
    main_py = REPO_ROOT / "src" / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"Pipeline entrypoint not found: {main_py}")

    env = os.environ.copy()
    env["START_DT"] = cfg.start_dt
    env["END_DT"] = cfg.end_dt
    env["SAMPLE_RATE"] = str(cfg.sample_rate)
    env["PROJECT_ID"] = cfg.project_id
    env["DATASET_ID"] = cfg.dataset_id
    env["FOLDER_NM"] = cfg.folder_nm

    process = subprocess.run(
        [SPARK_PYTHON, str(main_py)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        return {
            "status": "failed",
            "pipeline": "rnn_data_prep",
            "execution_mode": "subprocess",
            "parameters": cfg._dict_,
            "return_code": process.returncode,
            "stdout": process.stdout[-4000:],
            "stderr": process.stderr[-4000:],
        }

    return {
        "status": "completed",
        "pipeline": "rnn_data_prep",
        "execution_mode": "subprocess",
        "parameters": cfg._dict_,
        "stdout": process.stdout[-4000:],
    }

def run_rnn_data_prep(params: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _build_config(params)

    try:
        return _try_import_execution(cfg)
    except Exception as import_exc:
        try:
            return _try_subprocess_execution(cfg)
        except Exception as subprocess_exc:
            return {
                "status": "failed",
                "pipeline": "rnn_data_prep",
                "parameters": cfg._dict_,
                "message": "Failed to execute RNN data prep pipeline.",
                "import_execution_error": str(import_exc),
                "subprocess_execution_error": str(subprocess_exc),
                "traceback": traceback.format_exc()[-6000:],
            }