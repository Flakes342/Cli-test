from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re


CANONICAL_ALERT_TYPES = {
    "lower_limit_breach": ["lower limit", "lower-limit", "lower control", "below control", "drop alert", "sudden decline"],
    "upper_limit_breach": ["upper limit", "upper-limit", "upper control", "above control"],
    "count_alert": ["count alert", "count breach", "count"],
    "ratio_drop": ["ratio drop", "ratio decline", "decline", "drop"],
    "ratio_spike": ["ratio spike", "ratio jump", "spike", "jump"],
    "distribution_shift": ["distribution shift", "distribution change", "mix shift", "shift"],
}

METRIC_VIEW_MAP = {
    "count": ["count", "volume", "cnt"],
    "ratio": ["ratio", "rate", "pct", "percentage"],
}


@dataclass(frozen=True)
class ParsedAlertRequest:
    raw_user_query: str
    variable_reference: str
    alert_date: str
    alert_type: str
    metric_view: str
    model_hint: str
    segment_hint: str
    market_hint: str
    analyst_notes: str
    confidence: float


def parse_alert_query(user_query: str, *, today: date | None = None) -> ParsedAlertRequest:
    text = (user_query or "").strip()
    baseline_today = today or date.today()
    variable_reference = _extract_variable_reference(text)
    alert_date = _extract_alert_date(text, today=baseline_today)
    alert_type = _normalize_alert_type(text)
    metric_view = _extract_metric_view(text)
    model_hint = _extract_model_hint(text)
    segment_hint = _extract_segment_hint(text)
    market_hint = _extract_market_hint(text)
    confidence = _confidence_score(variable_reference=variable_reference, alert_date=alert_date, alert_type=alert_type)

    return ParsedAlertRequest(
        raw_user_query=text,
        variable_reference=variable_reference,
        alert_date=alert_date,
        alert_type=alert_type,
        metric_view=metric_view,
        model_hint=model_hint,
        segment_hint=segment_hint,
        market_hint=market_hint,
        analyst_notes=text,
        confidence=confidence,
    )


def _extract_variable_reference(text: str) -> str:
    direct_code = re.search(r"\b[A-Za-z]{2,}[A-Za-z0-9_]{2,}\d{1,4}\b", text)
    if direct_code:
        return direct_code.group(0)

    for marker in ("variable", "for", "rca for"):
        pattern = rf"{marker}\s+([a-zA-Z0-9_]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _extract_alert_date(text: str, *, today: date) -> str:
    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso_match:
        return iso_match.group(1)

    lowered = text.lower()
    if "yesterday" in lowered:
        return (today - timedelta(days=1)).isoformat()
    if "today" in lowered:
        return today.isoformat()

    month_match = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})\b", text)
    if month_match:
        month_name, day_str = month_match.groups()
        try:
            parsed = datetime.strptime(f"{month_name} {int(day_str)} {today.year}", "%b %d %Y").date()
        except ValueError:
            try:
                parsed = datetime.strptime(f"{month_name} {int(day_str)} {today.year}", "%B %d %Y").date()
            except ValueError:
                parsed = today
        return parsed.isoformat()

    return today.isoformat()


def _normalize_alert_type(text: str) -> str:
    lowered = text.lower()
    for canonical, variants in CANONICAL_ALERT_TYPES.items():
        if any(variant in lowered for variant in variants):
            return canonical
    if "control chart" in lowered or "breach" in lowered:
        return "distribution_shift"
    return "unknown"


def _extract_metric_view(text: str) -> str:
    lowered = text.lower()
    for view, variants in METRIC_VIEW_MAP.items():
        if any(variant in lowered for variant in variants):
            return view
    return "unknown"


def _extract_model_hint(text: str) -> str:
    known = ["xgboost", "rnn", "canceled plastic", "gen 13", "gen 4"]
    lowered = text.lower()
    matches = [value for value in known if value in lowered]
    return ", ".join(matches)


def _extract_segment_hint(text: str) -> str:
    known_segments = ["cm out of pattern", "authentication", "history", "enhanced authorization"]
    lowered = text.lower()
    for segment in known_segments:
        if segment in lowered:
            return segment
    return ""


def _extract_market_hint(text: str) -> str:
    market_match = re.search(r"\b(US|CA|MX|GB|DE|FR|IT|JP|AU|NZ|SG|HK|TH|TW)\b", text.upper())
    return market_match.group(1) if market_match else ""


def _confidence_score(*, variable_reference: str, alert_date: str, alert_type: str) -> float:
    score = 0.4
    if variable_reference:
        score += 0.25
    if alert_date:
        score += 0.2
    if alert_type != "unknown":
        score += 0.15
    return round(min(score, 0.99), 2)
