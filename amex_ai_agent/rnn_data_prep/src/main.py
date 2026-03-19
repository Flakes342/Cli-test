import sys
import os
from pathlib import Path

BASE_DIR = Path(_file_).resolve().parents[1]

sys.path.insert(0, str(BASE_DIR))
os.environ["PYTHONPATH"] = str(BASE_DIR) + ":" + os.environ.get("PYTHONPATH", "")

from pyspark.sql import SparkSession
from utils import lumi_utils
from utils import prep_utils
from datetime import datetime, timedelta

try:
    import os
    spark = SparkSession.builder.appName("test").getOrCreate()

#     os.environ["PYSPARK_PYTHON"] = sys.executable
#     os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

#     spark = (
#         SparkSession.builder
#         .appName("rnn_data_prep")
#         .config("spark.pyspark.python", sys.executable)
#         .config("spark.pyspark.driver.python", sys.executable)
#         .getOrCreate()
#     )
    spark.conf.set("viewsEnabled", "true")
    spark.conf.set("materializationDataset", "atanw9")
except Exception:
    raise

def run_pipeline(start_dt, end_dt, sample_rate, project_id="", dataset_id="", folder_nm=""):

    spark = SparkSession.builder.appName("rnn_data_prep").getOrCreate()

    start_dt_obj = datetime.strptime(start_dt, "%Y-%m-%d").date()
    start_dt_10 = (start_dt_obj - timedelta(days=10)).strftime("%Y-%m-%d")
    start_dt_20 = (start_dt_obj - timedelta(days=30)).strftime("%Y-%m-%d")

    print("Running SQL queries...")

    init_sql = open("rnn_data_prep/sqlQ/init_sample.txt").read().format(
        start_dt=start_dt,
        end_dt=end_dt,
        start_dt_10 = start_dt_10,
        start_dt_20 = start_dt_20,
        sample_rate=sample_rate
    )

    lumi_utils.create_table(init_sql, f"{project_id}.{dataset_id}.{folder_nm}_init_sample")

    exclusions_sql = open("rnn_data_prep/sqlQ/exclusions.txt").read().format(
        start_dt=start_dt,
        end_dt=end_dt,
        start_dt_10 = start_dt_10,
        start_dt_20 = start_dt_20,
        initial_data_id = f"{project_id}.{dataset_id}.{folder_nm}_init_sample"
    )

    lumi_utils.create_table(exclusions_sql, f"{project_id}.{dataset_id}.{folder_nm}_exclusions")

    seq_sql = open("rnn_data_prep/sqlQ/rnn_seq.txt").read().format(
        start_dt=start_dt,
        end_dt=end_dt,
        start_dt_10 = start_dt_10,
        start_dt_20 = start_dt_20,
        sample_caspkeys_id = f"{project_id}.{dataset_id}.{folder_nm}_exclusions"
    )

    lumi_utils.create_table(seq_sql, f"{project_id}.{dataset_id}.{folder_nm}_rnn_seq")

    vars_sql = open("rnn_data_prep/sqlQ/vars_pull.txt").read().format(
        start_dt=start_dt,
        end_dt=end_dt,
        start_dt_10 = start_dt_10,
        start_dt_20 = start_dt_20,
        rnn_seq_id = f"{project_id}.{dataset_id}.{folder_nm}_rnn_seq"
    )

    lumi_utils.create_table(vars_sql, f"{project_id}.{dataset_id}.{folder_nm}_vars_pull")

    print("Loading Spark dataframe...")

    df = prep_utils.create_df(
        spark,
        project_id,
        dataset_id,
        folder_nm,
        table_nm = 'vars_pull'
    )

    base = prep_utils.create_df(
        spark,
        project_id,
        dataset_id,
        folder_nm,
        table_nm = 'rnn_seq'
    )

    df_sample_cas_pkeys = prep_utils.create_df(
        spark,
        project_id,
        dataset_id,
        folder_nm,
        table_nm = 'exclusions'
    )

    print("Bucketing features...")

    df_bucket = prep_utils.dimension_bucketing(df)

    print("Creating RNN sequences...")

    output_path = f"gs://prj-p-ai-fraud/rnd/atanw9/sally-cat/{folder_nm}/{folder_nm}_rnn_training_data"

    final_df = prep_utils.rnn_data_seq_final(
        base=base,
        data=df_bucket,
        df_sample_cas_pkeys=df_sample_cas_pkeys,
        BASE_PATH=output_path,
        spark=spark)

    print("Writing dataset...")

    final_df.write.mode("overwrite").csv(output_path)

    return {
        "message": "RNN dataset created successfully",
        "output_path": output_path
    }