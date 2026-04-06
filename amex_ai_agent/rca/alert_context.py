from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VariableMetadata:
    variable_id: str
    variable_name: str = ""
    description: str = ""
    source_table: str = ""
    segment: str = ""
    model_family: str = ""
    use_case: str = ""
    variable_type: str = ""
    numerator_hint: str = ""
    denominator_hint: str = ""
    owner_team: str = ""
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AlertContext:
    raw_user_query: str
    resolved_variable_id: str
    resolved_variable_name: str
    alert_date: str
    alert_type: str
    metric_view: str
    parse_confidence: float
    start_date: str
    end_date: str
    baseline_start_date: str
    baseline_end_date: str
    model_hint: str = ""
    segment_hint: str = ""
    market_hint: str = ""
    analyst_notes: str = ""
