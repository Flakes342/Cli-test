from __future__ import annotations

from dataclasses import asdict

from amex_ai_agent.rca.alert_context import AlertContext, VariableMetadata


PIPELINE_STAGES = [
    "base",
    "with_zva",
    "with_ff",
    "noncanc",
    "nonzva",
    "dedupe",
    "with_poldec",
    "non_derived",
    "notfrap",
    "notff",
    "no_roc_v1",
    "no_roc_v2",
    "final_output",
]


def build_rca_output(
    *,
    context: AlertContext,
    metadata: VariableMetadata,
    observations: dict[str, object],
    sample_rate: float,
    stage_sql: str,
    driver_sql: dict[str, str],
) -> dict[str, object]:
    stage_diagnostics = _build_stage_diagnostics(observations)
    top_drivers = _build_top_drivers(observations)
    data_quality_checks = _build_dq_checks(observations)
    metric_decomposition = _build_metric_decomposition(metadata, observations)
    alert_summary = _build_alert_summary(context, observations)
    hypotheses = _rank_hypotheses(
        context=context,
        stage_diagnostics=stage_diagnostics,
        metric_decomposition=metric_decomposition,
        data_quality_checks=data_quality_checks,
        top_drivers=top_drivers,
    )

    return {
        "input_context": asdict(context),
        "resolved_variable_metadata": asdict(metadata),
        "analysis_window": {"start_date": context.start_date, "end_date": context.end_date},
        "baseline_window": {"start_date": context.baseline_start_date, "end_date": context.baseline_end_date},
        "alert_summary": alert_summary,
        "metric_decomposition": metric_decomposition,
        "stage_diagnostics": stage_diagnostics,
        "top_drivers": top_drivers,
        "data_quality_checks": data_quality_checks,
        "hypotheses": hypotheses,
        "analysis_sql": {"stage_funnel_sql": stage_sql, "driver_sql": driver_sql, "sample_rate": sample_rate},
        "analyst_summary": _analyst_summary(context, metadata, stage_diagnostics, hypotheses),
    }


def _build_alert_summary(context: AlertContext, observations: dict[str, object]) -> dict[str, object]:
    metric_value = _to_float(observations.get("metric_value"))
    baseline_value = _to_float(observations.get("baseline_value"))
    pct_change = _pct_change(metric_value, baseline_value)
    if context.alert_type in {"lower_limit_breach", "ratio_drop"}:
        direction = "down"
    elif context.alert_type in {"upper_limit_breach", "ratio_spike", "count_alert"}:
        direction = "up"
    else:
        direction = "unknown"
    return {
        "metric_value": metric_value,
        "baseline_value": baseline_value,
        "pct_change": pct_change,
        "alert_direction": direction,
    }


def _build_metric_decomposition(metadata: VariableMetadata, observations: dict[str, object]) -> dict[str, object]:
    numerator = {
        "label": metadata.numerator_hint or "numerator",
        "value": _to_float(observations.get("numerator_value")),
        "baseline": _to_float(observations.get("numerator_baseline")),
    }
    numerator["pct_change"] = _pct_change(numerator["value"], numerator["baseline"])

    denominator = {
        "label": metadata.denominator_hint or "denominator",
        "value": _to_float(observations.get("denominator_value")),
        "baseline": _to_float(observations.get("denominator_baseline")),
    }
    denominator["pct_change"] = _pct_change(denominator["value"], denominator["baseline"])

    return {"numerator": numerator, "denominator": denominator}


def _build_stage_diagnostics(observations: dict[str, object]) -> list[dict[str, object]]:
    observed_stage = observations.get("stage_counts")
    stage_counts = observed_stage if isinstance(observed_stage, dict) else {}

    diagnostics: list[dict[str, object]] = []
    lowest = 0.0
    lowest_stage = ""
    for stage in PIPELINE_STAGES:
        values = stage_counts.get(stage) if isinstance(stage_counts.get(stage), dict) else {}
        current_count = _to_float(values.get("current"))
        baseline_count = _to_float(values.get("baseline"))
        pct = _pct_change(current_count, baseline_count)
        if pct is not None and pct < lowest:
            lowest = pct
            lowest_stage = stage
        diagnostics.append(
            {
                "stage": stage,
                "current_count": current_count,
                "baseline_count": baseline_count,
                "pct_change": pct,
                "flagged": False,
            }
        )

    for item in diagnostics:
        if item["stage"] == lowest_stage and item["pct_change"] is not None and item["pct_change"] <= -0.1:
            item["flagged"] = True
    return diagnostics


def _build_top_drivers(observations: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    raw = observations.get("top_drivers")
    driver_payload = raw if isinstance(raw, dict) else {}
    keys = ["mcc", "country", "model_id", "lift_path", "approval_code", "cm15", "canceled_plastic", "zero_value_auth"]

    result: dict[str, list[dict[str, object]]] = {}
    for key in keys:
        value = driver_payload.get(key)
        result[key] = value if isinstance(value, list) else []
    return result


def _build_dq_checks(observations: dict[str, object]) -> list[dict[str, object]]:
    payload = observations.get("data_quality_checks")
    if isinstance(payload, list) and payload:
        checks: list[dict[str, object]] = []
        for item in payload:
            if isinstance(item, dict):
                checks.append(
                    {
                        "name": str(item.get("name", "unnamed_check")),
                        "status": str(item.get("status", "pass")),
                        "details": str(item.get("details", "")),
                    }
                )
        return checks

    return [
        {"name": "missing_key_fields", "status": "unknown", "details": "No missing-value profile provided."},
        {"name": "row_count_gap", "status": "unknown", "details": "No row count profile provided."},
        {"name": "ingestion_lag", "status": "unknown", "details": "No ingestion timestamps provided."},
    ]


def _rank_hypotheses(
    *,
    context: AlertContext,
    stage_diagnostics: list[dict[str, object]],
    metric_decomposition: dict[str, object],
    data_quality_checks: list[dict[str, object]],
    top_drivers: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    hypotheses: list[dict[str, object]] = []

    numerator = metric_decomposition["numerator"]
    denominator = metric_decomposition["denominator"]
    if isinstance(numerator.get("pct_change"), float) and numerator["pct_change"] < -0.1:
        hypotheses.append(
            {
                "hypothesis": "Numerator decline is driving the alert.",
                "confidence": 0.78,
                "evidence": [f"Numerator pct_change={numerator['pct_change']:.2%}"],
            }
        )
    if isinstance(denominator.get("pct_change"), float) and denominator["pct_change"] > 0.1:
        hypotheses.append(
            {
                "hypothesis": "Denominator inflation reduced the ratio.",
                "confidence": 0.72,
                "evidence": [f"Denominator pct_change={denominator['pct_change']:.2%}"],
            }
        )

    flagged = [item for item in stage_diagnostics if item.get("flagged")]
    if flagged:
        stage_name = str(flagged[0].get("stage", "unknown"))
        hypotheses.append(
            {
                "hypothesis": "Stage-specific filter or routing change introduced volume loss.",
                "confidence": 0.76,
                "evidence": [f"Largest funnel drop at stage={stage_name}"],
            }
        )

    dq_failures = [item for item in data_quality_checks if str(item.get("status", "")).lower() == "fail"]
    if dq_failures:
        names = ", ".join(str(item.get("name", "dq_issue")) for item in dq_failures)
        hypotheses.append(
            {
                "hypothesis": "Data quality or ingestion issue likely contributed to the alert.",
                "confidence": 0.8,
                "evidence": [f"Failed DQ checks: {names}"],
            }
        )

    if not hypotheses:
        hypotheses.append(
            {
                "hypothesis": "Potential mix-shift in segment or model routing.",
                "confidence": 0.55,
                "evidence": [
                    f"Alert type={context.alert_type}",
                    f"Driver buckets present: {', '.join(key for key, rows in top_drivers.items() if rows)}",
                ],
            }
        )

    return sorted(hypotheses, key=lambda item: float(item["confidence"]), reverse=True)


def _analyst_summary(
    context: AlertContext,
    metadata: VariableMetadata,
    stage_diagnostics: list[dict[str, object]],
    hypotheses: list[dict[str, object]],
) -> str:
    stage = next((item for item in stage_diagnostics if item.get("flagged")), None)
    stage_text = f"Largest funnel movement appears at stage '{stage['stage']}'." if stage else "No stage-level outlier is confirmed yet."
    top_hypothesis = hypotheses[0]["hypothesis"] if hypotheses else "No hypothesis generated"

    return (
        f"Initial RCA for {context.resolved_variable_id} ({context.resolved_variable_name}) on {context.alert_date} "
        f"classified as {context.alert_type}. {metadata.description or 'Definition unavailable in metadata.'} "
        f"{stage_text} Top likely cause: {top_hypothesis} "
        "Next checks: run stage_funnel_sql for alert and baseline windows, validate top driver buckets, and confirm ingestion completeness."
    )


def _pct_change(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline in (None, 0):
        return None
    return (value - baseline) / baseline


def _to_float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
