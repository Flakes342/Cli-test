from __future__ import annotations

from datetime import date

from amex_ai_agent.rca.alert_query_parser import parse_alert_query


def test_parse_alert_query_extracts_variable_date_and_type() -> None:
    parsed = parse_alert_query("RDMC3048 got a lower-limit alert on 2026-03-22", today=date(2026, 3, 30))

    assert parsed.variable_reference == "RDMC3048"
    assert parsed.alert_date == "2026-03-22"
    assert parsed.alert_type == "lower_limit_breach"


def test_parse_alert_query_resolves_relative_date_and_metric() -> None:
    parsed = parse_alert_query(
        "Canceled Plastic XGBoost Gen 13 variable RDMC3048 got COUNT alert yesterday",
        today=date(2026, 3, 30),
    )

    assert parsed.alert_date == "2026-03-29"
    assert parsed.metric_view == "count"
    assert "xgboost" in parsed.model_hint
