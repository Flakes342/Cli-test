from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from pyspark.sql import SparkSession


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
os.environ["PYTHONPATH"] = str(BASE_DIR) + ":" + os.environ.get("PYTHONPATH", "")

from utils import lumi_utils, prep_utils  # noqa: E402


LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[str], None] | None


def _emit(message: str, progress_callback: ProgressCallback = None) -> None:
    LOGGER.info(message)
    print(message)
    if progress_callback is not None:
        progress_callback(message)


def _load_sql(name: str) -> str:
    return (BASE_DIR / "sqlQ" / name).read_text(encoding="utf-8")


def _spark_python() -> str:
    return os.environ.get("RNN_SPARK_PYTHON") or os.environ.get("PYSPARK_PYTHON") or sys.executable


def _build_spark_session() -> SparkSession:
    spark_python = _spark_python()
    os.environ["RNN_SPARK_PYTHON"] = spark_python
    os.environ["PYSPARK_PYTHON"] = spark_python
    os.environ["PYSPARK_DRIVER_PYTHON"] = spark_python

    return (
        SparkSession.builder.appName("rnn_data_prep")
        .config("spark.pyspark.python", spark_python)
        .config("spark.pyspark.driver.python", spark_python)
        .getOrCreate()
    )


def run_pipeline(
    start_dt: str,
    end_dt: str,
    sample_rate: float,
    project_id: str = "",
    dataset_id: str = "",
    folder_nm: str = "",
    progress_callback: ProgressCallback = None,
) -> dict[str, str]:
    spark = _build_spark_session()
    spark.conf.set("viewsEnabled", "true")
    if dataset_id:
        spark.conf.set("materializationDataset", dataset_id)

    start_dt_obj = datetime.strptime(start_dt, "%Y-%m-%d").date()
    start_dt_10 = (start_dt_obj - timedelta(days=10)).strftime("%Y-%m-%d")
    start_dt_20 = (start_dt_obj - timedelta(days=30)).strftime("%Y-%m-%d")

    init_table = f"{project_id}.{dataset_id}.{folder_nm}_init_sample"
    exclusions_table = f"{project_id}.{dataset_id}.{folder_nm}_exclusions"
    seq_table = f"{project_id}.{dataset_id}.{folder_nm}_rnn_seq"
    vars_table = f"{project_id}.{dataset_id}.{folder_nm}_vars_pull"

    _emit("Creating init sample table...", progress_callback)
    lumi_utils.create_table(
        _load_sql("init_sample.txt").format(
            start_dt=start_dt,
            end_dt=end_dt,
            start_dt_10=start_dt_10,
            start_dt_20=start_dt_20,
            sample_rate=sample_rate,
        ),
        init_table,
    )

    _emit("Creating exclusions table...", progress_callback)
    lumi_utils.create_table(
        _load_sql("exclusions.txt").format(
            start_dt=start_dt,
            end_dt=end_dt,
            start_dt_10=start_dt_10,
            start_dt_20=start_dt_20,
            initial_data_id=init_table,
        ),
        exclusions_table,
    )

    _emit("Creating RNN sequence table...", progress_callback)
    lumi_utils.create_table(
        _load_sql("rnn_seq.txt").format(
            start_dt=start_dt,
            end_dt=end_dt,
            start_dt_10=start_dt_10,
            start_dt_20=start_dt_20,
            sample_caspkeys_id=exclusions_table,
        ),
        seq_table,
    )

    _emit("Creating vars pull table...", progress_callback)
    lumi_utils.create_table(
        _load_sql("vars_pull.txt").format(
            start_dt=start_dt,
            end_dt=end_dt,
            start_dt_10=start_dt_10,
            start_dt_20=start_dt_20,
            rnn_seq_id=seq_table,
        ),
        vars_table,
    )

    _emit("Creating Spark dataframes...", progress_callback)
    df = prep_utils.create_df(spark, project_id, dataset_id, folder_nm, table_nm="vars_pull")
    base = prep_utils.create_df(spark, project_id, dataset_id, folder_nm, table_nm="rnn_seq")
    df_sample_cas_pkeys = prep_utils.create_df(
        spark, project_id, dataset_id, folder_nm, table_nm="exclusions"
    )

    _emit("Bucketing features...", progress_callback)
    df_bucket = prep_utils.dimension_bucketing(df)

    _emit("Creating RNN sequences...", progress_callback)
    output_path = f"gs://{project_id}/rnd/{dataset_id}/sally-cat/{folder_nm}/{folder_nm}_rnn_training_data"
    final_df = prep_utils.rnn_data_seq_final(
        base=base,
        data=df_bucket,
        df_sample_cas_pkeys=df_sample_cas_pkeys,
        BASE_PATH=output_path,
        spark=spark,
    )

    _emit("Writing dataset...", progress_callback)
    final_df.write.mode("overwrite").csv(output_path)

    return {
        "message": "RNN dataset created successfully.",
        "output_path": output_path,
        "tables": ", ".join([init_table, exclusions_table, seq_table, vars_table]),
    }


if __name__ == "__main__":
    run_pipeline(
        start_dt=os.environ["START_DT"],
        end_dt=os.environ["END_DT"],
        sample_rate=float(os.environ.get("SAMPLE_RATE", "0.025")),
        project_id=os.environ.get("PROJECT_ID", ""),
        dataset_id=os.environ.get("DATASET_ID", ""),
        folder_nm=os.environ.get("FOLDER_NM", "rnn_data_prep"),
    )
