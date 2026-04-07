from __future__ import annotations

from amex_ai_agent.rca.alert_context import AlertContext, VariableMetadata
from amex_ai_agent.rca.analysis import build_rca_output


def test_build_rca_output_flags_stage_and_hypothesis() -> None:
    context = AlertContext(
        raw_user_query="RDMC3048 lower-limit alert",
        resolved_variable_id="RDMC3048",
        resolved_variable_name="cmmccd48_mccd30_ratio",
        alert_date="2026-03-22",
        alert_type="lower_limit_breach",
        metric_view="count",
        parse_confidence=0.95,
        start_date="2026-03-20",
        end_date="2026-03-22",
        baseline_start_date="2026-02-21",
        baseline_end_date="2026-03-19",
    )
    metadata = VariableMetadata(
        variable_id="RDMC3048",
        variable_name="cmmccd48_mccd30_ratio",
        description="ratio definition",
        numerator_hint="approved_amt_48h",
        denominator_hint="mcc_amt_30_396",
    )
    output = build_rca_output(
        context=context,
        metadata=metadata,
        observations={
            "metric_value": 0.12,
            "baseline_value": 0.18,
            "numerator_value": 120,
            "numerator_baseline": 190,
            "denominator_value": 1000,
            "denominator_baseline": 980,
            "stage_counts": {
                "base": {"current": 10000, "baseline": 9800},
                "noncanc": {"current": 6500, "baseline": 9000},
                "final_output": {"current": 6000, "baseline": 8800},
            },
            "data_quality_checks": [{"name": "date_gap", "status": "pass", "details": "no gaps"}],
        },
        sample_rate=0.025,
        stage_sql="SELECT 1",
        driver_sql={"mcc": "SELECT 1"},
    )

    flagged = [item for item in output["stage_diagnostics"] if item["flagged"]]
    assert flagged
    assert output["hypotheses"]
    assert output["alert_summary"]["alert_direction"] == "down"
