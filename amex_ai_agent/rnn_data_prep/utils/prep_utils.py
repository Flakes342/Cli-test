import logging
import time
from typing import Optional

import numpy as np
import pandas as pd

import pyspark
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.functions import (
    col,
    udf,
    datediff,
    to_date,
    lit,
    struct,
    rand,
    split,
)
from pyspark.sql.types import DateType, StringType, IntegerType, DoubleType

logger = logging.getLogger(_name_)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_df(spark: SparkSession, project_id: str, dataset_id: str, folder_nm: str, table_nm: str):
    """
    Create a PySpark DataFrame from a BigQuery table.

    The Spark BigQuery connector expects a 'query' option when passing raw SQL strings.
    This helper builds a simple "SELECT * FROM <table_nm>;" query and loads it.

    Parameters
    ----------
    spark : SparkSession
        Active Spark session configured with the BigQuery connector.
    table_nm : str
        Fully-qualified BigQuery table name (project.dataset.table).

    Returns
    -------
    DataFrame | None
        Spark DataFrame on success, None on error (errors are logged).
    """
    query = f"select * from {project_id}.{dataset_id}.{folder_nm}_{table_nm};"
    logger.info("Creating pyspark dataframe from BigQuery. table_nm=%s", table_nm)
    try:
        df = (
            spark.read.format("bigquery")
            # BigQuery connector expects 'query' for SQL strings
            .option("query", query)
            .load()
        )
        logger.info("df created successfully. columns=%d", len(df.columns))
        return df
    except Exception:
        # Preserve previous behavior: log exception and return None
        logger.exception("Error happened while creating pyspark dataframe for table_nm=%s", table_nm)
        return None


# ------------------------------
# Mapping functions (return integer codes)
# ------------------------------
# Each mapping function accepts a list/tuple-like input 'v' and computes a single integer
# encoding according to business rules. They were preserved mostly as-is; docstrings/comments
# briefly describe intent for each mapping function.

# Internal Logics cant display the full code for the mapping functions due to length, but they follow a similar pattern:
# - Each function takes a list/tuple 'v' as input, which contains relevant fields for the mapping logic.
# - The functions apply specific business rules to compute an integer code based on the input values. 

# ------------------------------
# Dimension bucketing (wrap as UDFs and apply)
# ------------------------------
def dimension_bucketing(data):
    """
    Add *_buc_3b bucket columns to the DataFrame and return a reduced dataframe.

    - Registers UDFs for each mapping function above
    - Applies them using struct(...) to pass multiple columns into each UDF
    - Returns a reduced dataframe containing only: cas_pkey + bucket columns + age_in_days
    """
    logger.info("Starting dimension_bucketing().")
    try:
        # Register UDFs (IntegerType outputs)
        aav_buc_udf = udf(aav_map, IntegerType())
        disruption_buc_udf = udf(disruption_map, IntegerType())
        email_buc_udf = udf(email_map, IntegerType())
        ftg_buc_udf = udf(ftg_map, IntegerType())
        indusamt_buc_udf = udf(indusamt_map, IntegerType())
        ip_buc_udf = udf(ip_map, IntegerType())
        location_buc_udf = udf(location_map, IntegerType())
        time_buc_udf = udf(time_map, IntegerType())
        onword_buc_udf = udf(onword_map, IntegerType())
        phone_buc_udf = udf(phone_map, IntegerType())
        seprn_buc_udf = udf(seprn_map, IntegerType())
        sepry_buc_udf = udf(sepry_map, IntegerType())
        stcd_buc_udf = udf(stcd_map, IntegerType())
        txn_att_buc_udf = udf(txn_att_map, IntegerType())
        topmaps_buc_udf = udf(topmaps_map, IntegerType())
        velocity_buc_udf = udf(velocity_map, IntegerType())
        cm_char_buc_udf = udf(cm_char_map, IntegerType())

        # Apply mapping UDFs. Passing structs to UDFs keeps the same signature as mapping functions.
        data = data.withColumn("aav_buc_3b", aav_buc_udf(struct("AAVMDLCD", "DYSSNCSA", "DYSSNCMA", "BILADT30", "NSBLADSC")))
        data = data.withColumn("disruption_buc_3b", disruption_buc_udf(struct("MINSNASG", "MDMTCASG", "HRSIDOV", "RESIDSE", "OVCNTFTG", "SRCOVRRD")))
        data = data.withColumn("email_buc_3b", email_buc_udf(struct("CUDEM30P", "EMNMMRCD", "DYSSNCNE", "IPTOCSEM", "NE04CT24", "NSEMLSC", "EMUCM2D")))
        data = data.withColumn("ftg_buc_3b", ftg_buc_udf(struct("SERLLFTG", "WLSE7FTG", "CWLSEFTG", "TMIDFTG", "CNFFTG48", "CONFSE48", "SEZVAFTG", "ZVAIND", "AMOUNT", "CONV_AMT")))
        data = data.withColumn("indusamt_buc_3b", indusamt_buc_udf(struct("S_BFS_CD", "AMOUNT", "SBFSD30", "CUDVEVDI", "ZVAIND", "CONV_AMT")))
        data = data.withColumn("ip_buc_3b", ip_buc_udf(struct("CUIP2D30", "CUIP4D30", "NE08CT24", "IPUCM2H", "IPDISTHM")))
        data = data.withColumn("location_buc_3b", location_buc_udf(struct("DISTCMSE", "DISTCHIP", "MNDIST30", "SE3HOT7", "TRSE3IND", "DISTSESE", "DSCIDCR", "RSZT4815")))
        # age_in_days calculation (example/reference date was used in original):
        data = data.withColumn("age_in_days", datediff(to_date(lit("2021-01-01")), col("TRANS_DT")))
        data = data.withColumn("time_buc_3b", time_buc_udf(struct("TMOFDYIN", "WKNDIND", "NIGHTIND", "CNTRY_CD")))
        data = data.withColumn("onword_buc_3b", onword_buc_udf(struct("EAPNMMI", "AIRNMT30", "MDISTAIR")))
        data = data.withColumn("phone_buc_3b", phone_buc_udf(struct("CMPHBL30", "DCPPHNCM", "DYSSNCPN", "NSBLPHSC", "CMNEG10D", "CNTANI7D", "CNTCM7D")))
        data = data.withColumn("seprn_buc_3b", seprn_buc_udf(struct("SEPRNMAX", "SECNT48", "NEWRF12", "TIMESCR")))
        data = data.withColumn("sepry_buc_3b", sepry_buc_udf(struct("RDSE305D", "SMAMT12", "SEPRYAVG", "NCHRATIO")))
        data = data.withColumn("stcd_buc_3b", stcd_buc_udf(struct("DYSSNC79", "DYSSNC44", "DYSSNC57", "DYSSNCVP", "DYSSNCT1")))
        data = data.withColumn("txn_att_buc_3b", txn_att_buc_udf(struct("TXNMDIND", "CIDMTHCD", "BTOBIND", "CDLGER31", "SRCUED10")))
        data = data.withColumn("topmaps_buc_3b", topmaps_buc_udf(struct("TOPMAPIN", "MAPD30", "SE5DAMT", "CMD5")))
        data = data.withColumn("velocity_buc_3b", velocity_buc_udf(struct("HRSRGTOC", "SE5DCNT", "CMN5", "TIMESESE")))
        data = data.withColumn("cm_char_buc_3b", cm_char_buc_udf(struct("DSACTEFF", "SOWYRDB", "TAAMT30", "GPRODUCT", "CASHIRT")))

        # Select reduced header (cas_pkey + bucketed features)
        hdr = [
            "cas_pkey",
            "aav_buc_3b",
            "disruption_buc_3b",
            "email_buc_3b",
            "ftg_buc_3b",
            "indusamt_buc_3b",
            "ip_buc_3b",
            "location_buc_3b",
            "age_in_days",
            "time_buc_3b",
            "onword_buc_3b",
            "phone_buc_3b",
            "seprn_buc_3b",
            "sepry_buc_3b",
            "stcd_buc_3b",
            "txn_att_buc_3b",
            "topmaps_buc_3b",
            "velocity_buc_3b",
            "cm_char_buc_3b",
        ]
        data = data[hdr]
        logger.info("dimension_bucketing() completed. columns=%d", len(data.columns))
        return data
    except Exception:
        logger.exception("dimension_bucketing() failed.")
        raise


# ------------------------------
# Helpers used during sequence assembly
# ------------------------------
def plus_one(v):
    """
    Left-pad the list to length 10 with zeros and return comma-separated string.

    Example:
        [2,3] -> '0,0,0,0,0,0,0,0,2,3'
    """
    v = [0] * (10 - len(v)) + v
    return ",".join([str(x) for x in v])


plus_one_udf = udf(plus_one, StringType())


def plus_one_ngt(v):
    """
    Special left-pad + NGT (non-global-time) adjustment used for age/time combined lists.

    Input 'v' is expected to be a struct-like where:
      v[0] = list1 (age list)
      v[1] = list2 (hours list)

    Logic:
      - Right-align last 10 values from list1/list2 using a default fill
      - Compute days difference relative to last element
      - Zero-out entries where days > 30
      - Add hours back to days
      - Return comma-separated string
    """
    list1 = v[0]
    list2 = v[1]
    x = ([1000] * 9 + list1)[-10:]
    hrs = ([0] * 9 + list2)[-10:]
    last_elem = x[-1]
    days = [a - last_elem + 1 for a in x]
    idx = 0
    while idx < 10:
        if days[idx] > 30:
            days[idx] = 0
            hrs[idx] = 0
        else:
            break
        idx += 1
    for itr_hr in range(10):
        days[itr_hr] = days[itr_hr] + hrs[itr_hr]
    return ",".join([str(x) for x in days])


plus_one_ngt_udf = udf(plus_one_ngt, StringType())

# ------------------------------
# Final sequence builder & writer
# ------------------------------
def rnn_data_seq_final(
    base,
    data,
    df_sample_cas_pkeys,
    BASE_PATH: str,
    spark: Optional[SparkSession] = None,
):
    """
    Build final RNN-ready sequences and write CSV output.

    Steps:
    1. Register temp views for 'base' (mapping), 'data' (features), and 'df_sample_cas_pkeys' (keys+labels).
    2. Join base->data on cas_pkey_hist and keep only sample keys (inner join).
    3. Use windowed collect_list(...) over partition by cas_pkey ordered by seq_hist to build
       incremental lists of historical values per cas_pkey.
    4. Keep only rows where seq_hist == seq (the 'current' row for each cas_pkey).
    5. Apply plus_one / plus_one_ngt UDFs to produce fixed-length (10) comma strings.
    6. Split comma strings into 10 individual integer columns per feature.
    7. Write final DataFrame to {BASE_PATH}/data as CSV (no header).

    Parameters
    ----------
    base : DataFrame
        Mapping DataFrame (current txn -> historical txn rows). Expected columns include:
        cas_pkey, cas_pkey_hist, seq, seq_hist, trans_dt, trans_dt_hist, etc.
    data : DataFrame
        Wide feature table keyed by cas_pkey (raw features + analytics).
    df_sample_cas_pkeys : DataFrame
        Sample keys DataFrame containing cas_pkey and lift_frd_in (label).
    BASE_PATH : str
        GCS base path where final CSV is written (must end with '/').
    spark : SparkSession, optional
        Spark session (if None, will be obtained with SparkSession.builder.getOrCreate()).

    Returns
    -------
    None
        Writes CSV to disk/GCS and returns None. Exceptions are raised on failures.
    """
    # Ensure spark is available
    if spark is None:
        spark = SparkSession.builder.getOrCreate()

    logger.info("Starting rnn_data_seq_final(). BASE_PATH=%s", BASE_PATH)

    try:
        # Create temp views used by SQL below
        base.createOrReplaceTempView("base")
        data.createOrReplaceTempView("data")
        df_sample_cas_pkeys.createOrReplaceTempView("df_sample_cas_pkeys")
        logger.info("Temp views created: base, data, df_sample_cas_pkeys")
    except Exception:
        logger.exception("Failed while creating temp views.")
        raise

    try:
        # Join mapping to feature table and to sample keys (keep only sampled keys)
        joined = spark.sql(
            """
            SELECT distinct
                a.*,
                b.aav_buc_3b,
                b.disruption_buc_3b,
                b.email_buc_3b,
                b.ftg_buc_3b,
                b.indusamt_buc_3b,
                b.ip_buc_3b,
                b.location_buc_3b,
                b.age_in_days,
                b.time_buc_3b,
                b.onword_buc_3b,
                b.phone_buc_3b,
                b.seprn_buc_3b,
                b.sepry_buc_3b,
                b.stcd_buc_3b,
                b.txn_att_buc_3b,
                b.topmaps_buc_3b,
                b.velocity_buc_3b,
                b.cm_char_buc_3b,
                c.lift_frd_in
            from base a
            inner join data b
            on a.cas_pkey_hist = b.cas_pkey
            inner join df_sample_cas_pkeys c
            on a.cas_pkey = c.cas_pkey
            """
        )
        joined.createOrReplaceTempView("joined")
        logger.info("Joined view created.")
    except Exception:
        logger.exception("Failed during join SQL step.")
        raise

    try:
        # Collect lists of bucketed features over history (window collect_list)
        # We use windowed collect_list via SQL "collect_list(...) over (partition by ... order by ...)"
        collected = spark.sql(
            """
            SELECT *
            from
            (
                SELECT
                    cas_pkey,
                    seq_hist,
                    seq,
                    lift_frd_in,
                    collect_list(aav_buc_3b) over (partition by cas_pkey order by seq_hist) as aav_collect_3b,
                    collect_list(disruption_buc_3b) over (partition by cas_pkey order by seq_hist) as disruption_collect_3b,
                    collect_list(email_buc_3b) over (partition by cas_pkey order by seq_hist) as email_collect_3b,
                    collect_list(ftg_buc_3b) over (partition by cas_pkey order by seq_hist) as ftg_collect_3b,
                    collect_list(indusamt_buc_3b) over (partition by cas_pkey order by seq_hist) as indusamt_collect_3b,
                    collect_list(ip_buc_3b) over (partition by cas_pkey order by seq_hist) as ip_collect_3b,
                    collect_list(location_buc_3b) over (partition by cas_pkey order by seq_hist) as location_collect_3b,
                    collect_list(age_in_days) over (partition by cas_pkey order by seq_hist) as age_in_days_collect_3b,
                    collect_list(time_buc_3b) over (partition by cas_pkey order by seq_hist) as time_collect_3b,
                    collect_list(onword_buc_3b) over (partition by cas_pkey order by seq_hist) as onword_collect_3b,
                    collect_list(phone_buc_3b) over (partition by cas_pkey order by seq_hist) as phone_collect_3b,
                    collect_list(seprn_buc_3b) over (partition by cas_pkey order by seq_hist) as seprn_collect_3b,
                    collect_list(sepry_buc_3b) over (partition by cas_pkey order by seq_hist) as sepry_collect_3b,
                    collect_list(stcd_buc_3b) over (partition by cas_pkey order by seq_hist) as stcd_collect_3b,
                    collect_list(txn_att_buc_3b) over (partition by cas_pkey order by seq_hist) as txn_att_collect_3b,
                    collect_list(topmaps_buc_3b) over (partition by cas_pkey order by seq_hist) as topmaps_collect_3b,
                    collect_list(velocity_buc_3b) over (partition by cas_pkey order by seq_hist) as velocity_collect_3b,
                    collect_list(cm_char_buc_3b) over (partition by cas_pkey order by seq_hist) as cm_char_collect_3b
                from joined
            )
            where seq_hist = seq
            """
        )
        logger.info("Collected dataframe created.")
    except Exception:
        logger.exception("Failed during collect/window SQL step.")
        raise

    try:
        # Convert collected lists into fixed-length comma-delimited strings using the UDFs
        collected = collected.withColumn("aav2_collect_3b_1", plus_one_udf(col("aav_collect_3b")))
        collected = collected.withColumn("disruption_collect_3b_1", plus_one_udf(col("disruption_collect_3b")))
        collected = collected.withColumn("email_collect_3b_1", plus_one_udf(col("email_collect_3b")))
        collected = collected.withColumn("ftg_collect_3b_1", plus_one_udf(col("ftg_collect_3b")))
        collected = collected.withColumn("indusamt_collect_3b_1", plus_one_udf(col("indusamt_collect_3b")))
        collected = collected.withColumn("ip_collect_3b_1", plus_one_udf(col("ip_collect_3b")))
        collected = collected.withColumn("location_collect_3b_1", plus_one_udf(col("location_collect_3b")))
        collected = collected.withColumn("onword_collect_3b_1", plus_one_udf(col("onword_collect_3b")))
        collected = collected.withColumn("phone_collect_3b_1", plus_one_udf(col("phone_collect_3b")))
        collected = collected.withColumn("seprn_collect_3b_1", plus_one_udf(col("seprn_collect_3b")))
        collected = collected.withColumn("sepry_collect_3b_1", plus_one_udf(col("sepry_collect_3b")))
        collected = collected.withColumn("stcd2_collect_3b_1", plus_one_udf(col("stcd_collect_3b")))
        collected = collected.withColumn("txn_att_collect_3b_1", plus_one_udf(col("txn_att_collect_3b")))
        collected = collected.withColumn("topmaps_collect_3b_1", plus_one_udf(col("topmaps_collect_3b")))
        collected = collected.withColumn("ngttime_collect_3b_1", plus_one_ngt_udf(struct("age_in_days_collect_3b", "time_collect_3b")))
        collected = collected.withColumn("velocity_collect_3b_1", plus_one_udf(col("velocity_collect_3b")))
        collected = collected.withColumn("cm_char_collect_3b_1", plus_one_udf(col("cm_char_collect_3b")))
        logger.info("Post-processing (plus_one/plus_one_ngt) columns created.")
    except Exception:
        logger.exception("Failed during plus_one/plus_one_ngt column creation.")
        raise

    try:
        # Select final header and rename to generic column names for expansion
        hdr2 = [
            "cas_pkey",
            "aav2_collect_3b_1",
            "disruption_collect_3b_1",
            "email_collect_3b_1",
            "ftg_collect_3b_1",
            "indusamt_collect_3b_1",
            "ip_collect_3b_1",
            "location_collect_3b_1",
            "onword_collect_3b_1",
            "phone_collect_3b_1",
            "seprn_collect_3b_1",
            "sepry_collect_3b_1",
            "stcd2_collect_3b_1",
            "txn_att_collect_3b_1",
            "topmaps_collect_3b_1",
            "ngttime_collect_3b_1",
            "velocity_collect_3b_1",
            "cm_char_collect_3b_1",
            "lift_frd_in",
        ]
        collected = collected[hdr2]

        # Rename columns to generic col_0..col_N (keeps logic unchanged and simplifies downstream)
        df = collected.toDF(*[f"col_{i}" for i in range(len(collected.columns))])

        key_col = "col_0"
        lift_col = f"col_{len(collected.columns)-1}"
        cols_to_expand = [f"col_{i}" for i in range(1, len(collected.columns)-1)]

        df_expanded = df
        expanded_cols_order = []

        # Expand each comma-separated sequence column into 10 integer columns
        for c in cols_to_expand:
            # Split the comma string into an array of strings
            df_expanded = df_expanded.withColumn(c, split(col(c), ","))
            # Create columns c_1 .. c_10 from array items (cast to Integer)
            for i in range(10):
                new_col = f"{c}_{i+1}"
                df_expanded = df_expanded.withColumn(new_col, col(c).getItem(i).cast(IntegerType()))
                expanded_cols_order.append(new_col)
            # Drop the array/string column after expansion
            df_expanded = df_expanded.drop(c)

        # Final column order: key, all expanded feature columns, label
        final_column_order = [key_col] + expanded_cols_order + [lift_col]
        df_final = df_expanded.select(final_column_order)
        logger.info("Final expanded dataframe ready. columns=%d", len(df_final.columns))
    except Exception:
        logger.exception("Failed during expansion/splitting into 10 columns each.")
        raise

    try:
        # Write final CSV to BASE_PATH/data (no header). Uses Spark CSV writer.
        (
            df_final.write.format("csv")
            .options(header="false", delimiter=",", nullValue=None, emptyValue=None)
            .save(f"{BASE_PATH}/data")
        )
        logger.info("Write completed successfully to %s/data", BASE_PATH)
    except Exception:
        logger.exception("Failed while writing output CSV to %s/data", BASE_PATH)
        raise

    # Function returns None (side-effect: writes CSV).
    return

