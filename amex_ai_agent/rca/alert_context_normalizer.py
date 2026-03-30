from __future__ import annotations

from datetime import date, timedelta

from amex_ai_agent.rca.alert_context import AlertContext
from amex_ai_agent.rca.alert_query_parser import ParsedAlertRequest


def normalize_alert_context(
    parsed: ParsedAlertRequest,
    *,
    resolved_variable_id: str,
    resolved_variable_name: str,
    alert_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    baseline_start_date: str | None = None,
    baseline_end_date: str | None = None,
) -> AlertContext:
    anchor = date.fromisoformat(alert_date or parsed.alert_date)

    analysis_end = date.fromisoformat(end_date) if end_date else anchor
    analysis_start = date.fromisoformat(start_date) if start_date else analysis_end - timedelta(days=2)

    baseline_end = date.fromisoformat(baseline_end_date) if baseline_end_date else analysis_start - timedelta(days=1)
    baseline_start = date.fromisoformat(baseline_start_date) if baseline_start_date else baseline_end - timedelta(days=27)

    return AlertContext(
        raw_user_query=parsed.raw_user_query,
        resolved_variable_id=resolved_variable_id,
        resolved_variable_name=resolved_variable_name,
        alert_date=anchor.isoformat(),
        alert_type=parsed.alert_type,
        metric_view=parsed.metric_view,
        parse_confidence=parsed.confidence,
        start_date=analysis_start.isoformat(),
        end_date=analysis_end.isoformat(),
        baseline_start_date=baseline_start.isoformat(),
        baseline_end_date=baseline_end.isoformat(),
        model_hint=parsed.model_hint,
        segment_hint=parsed.segment_hint,
        market_hint=parsed.market_hint,
        analyst_notes=parsed.analyst_notes,
    )
