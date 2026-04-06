from __future__ import annotations

from textwrap import dedent


def render_stage_funnel_sql(*, start_date: str, end_date: str, sample_rate: float) -> str:
    return dedent(
        f"""
        WITH base AS (
          SELECT
            a.cas_pkey,
            a.cm15,
            a.cm13,
            a.appr_deny_cd,
            a.trans_dt,
            a.amount,
            a.cancl_plastic_cd AS plstcnci,
            COALESCE(b.lift_frd_in,0) AS lift_frd_in,
            b.modl_id,
            b.lift_path_ds,
            b.first_id_dt
          FROM axp-lumi.dw.wwcas_authorization a
          LEFT JOIN axp-lumi.dw.lift_fraud_markings b
            ON a.cas_pkey = b.cas_pkey AND a.trans_dt = b.trans_dt
          WHERE a.trans_dt BETWEEN '{start_date}' AND '{end_date}'
            AND a.arm_proc_ind = '1'
            AND COALESCE(lift_frd_in,0) + RAND() >= (1-{sample_rate})
            AND (first_id_dt IS NULL OR first_id_dt <= DATE_ADD(DATE '{end_date}', INTERVAL 21 DAY))
        ),
        with_zva AS (
          SELECT a.*, b.zero_value_auth_ind
          FROM base a
          INNER JOIN axp-lumi.dw.wwcas_auth_analytics_01 b
            ON a.cas_pkey = b.cas_pkey AND a.trans_dt = b.trans_dt
        ),
        with_ff AS (
          SELECT
            a.*,
            CASE WHEN appr_deny_cd IN ('0','1','6') THEN 1 ELSE 0 END AS app_flag
          FROM with_zva a
        ),
        noncanc AS (SELECT * FROM with_ff WHERE plstcnci = 'false'),
        nonzva AS (
          SELECT *
          FROM noncanc
          WHERE CAST(zero_value_auth_ind AS INT64) = 0 OR zero_value_auth_ind IS NULL
        ),
        dedupe AS (
          SELECT a.*
          FROM nonzva a
          LEFT JOIN axp-lumi.dw.authddp_cas_credit_flag b ON a.cas_pkey = b.cas_pkey
          WHERE b.cas_pkey IS NULL
        ),
        with_poldec AS (
          SELECT
            a.*,
            CASE WHEN b.referral_rsn_cd IN ('01','03','06','09','11','14','18') THEN 1 ELSE 0 END AS poldec_flag
          FROM dedupe a
          LEFT JOIN axp-lumi.dw.authddp_referral_reason_code b ON a.cas_pkey = b.cas_pkey
        ),
        non_derived AS (SELECT * FROM with_poldec WHERE poldec_flag <> 1),
        notfrap AS (
          SELECT a.*
          FROM non_derived a
          LEFT JOIN (
            SELECT DISTINCT cm13 FROM axp-lumi.dw.lift_frap_data WHERE frap_in = 1
          ) b ON a.cm13 = b.cm13
          WHERE b.cm13 IS NULL
        ),
        notff AS (
          SELECT *
          FROM notfrap
          WHERE NOT (
            lift_frd_in = 1
            AND SUBSTR(lift_path_ds,1,2) IN ('1.', '3.')
            AND amount <= 50
          )
        )
        SELECT 'base' AS stage, COUNT(*) AS row_count FROM base UNION ALL
        SELECT 'with_zva', COUNT(*) FROM with_zva UNION ALL
        SELECT 'with_ff', COUNT(*) FROM with_ff UNION ALL
        SELECT 'noncanc', COUNT(*) FROM noncanc UNION ALL
        SELECT 'nonzva', COUNT(*) FROM nonzva UNION ALL
        SELECT 'dedupe', COUNT(*) FROM dedupe UNION ALL
        SELECT 'with_poldec', COUNT(*) FROM with_poldec UNION ALL
        SELECT 'non_derived', COUNT(*) FROM non_derived UNION ALL
        SELECT 'notfrap', COUNT(*) FROM notfrap UNION ALL
        SELECT 'notff', COUNT(*) FROM notff;
        """
    ).strip()


def render_driver_sql(*, start_date: str, end_date: str, dimension: str) -> str:
    dimension_col = {
        "mcc": "cm11",
        "country": "country_cd",
        "model_id": "modl_id",
        "lift_path": "lift_path_ds",
    }.get(dimension, dimension)
    return dedent(
        f"""
        SELECT {dimension_col} AS segment_value, COUNT(*) AS cnt, SUM(amount) AS total_amt
        FROM axp-lumi.dw.wwcas_authorization
        WHERE trans_dt BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1
        ORDER BY cnt DESC
        LIMIT 25
        """
    ).strip()
