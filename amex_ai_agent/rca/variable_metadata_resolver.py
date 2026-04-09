from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from amex_ai_agent.rca.alert_context import VariableMetadata
from amex_ai_agent.variable_catalog import normalize_text, normalize_token, normalize_value


COLUMN_ALIASES = {
    "variable": "variable_id",
    "variable_id": "variable_id",
    "id": "variable_id",
    "full_name": "variable_name",
    "variable_name": "variable_name",
    "name": "variable_name",
    "description": "description",
    "business_definition": "description",
    "table": "source_table",
    "source_table": "source_table",
    "domain": "segment",
    "segment": "segment",
    "model": "model_family",
    "model_family": "model_family",
    "use_case": "use_case",
    "portfolio": "use_case",
    "variable_type": "variable_type",
    "type": "variable_type",
    "default_value": "default_value",
    "default": "default_value",
    "numerator": "numerator_hint",
    "numerator_hint": "numerator_hint",
    "denominator": "denominator_hint",
    "denominator_hint": "denominator_hint",
    "owner": "owner_team",
    "owner_team": "owner_team",
    "aliases": "aliases",
    "alias": "aliases",
    "synonyms": "aliases",
    "synonym": "aliases",
    "tags": "tags",
}


class VariableMetadataResolver:
    def __init__(self, records: Iterable[VariableMetadata], source_path: str | Path = "") -> None:
        self.records = list(records)
        self.source_path = str(source_path)

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> "VariableMetadataResolver":
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        records = [record_from_row(row) for row in rows if row]
        return cls(records, source_path=path)

    def resolve(self, reference: str) -> tuple[VariableMetadata | None, list[VariableMetadata]]:
        token = normalize_token(reference)
        if not token:
            return None, []

        exact_matches = [record for record in self.records if token in {normalize_token(record.variable_id), normalize_token(record.variable_name)}]
        if len(exact_matches) == 1:
            return exact_matches[0], exact_matches
        if len(exact_matches) > 1:
            return None, exact_matches

        alias_matches = [record for record in self.records if token in {normalize_token(alias) for alias in record.aliases}]
        if len(alias_matches) == 1:
            return alias_matches[0], alias_matches
        if len(alias_matches) > 1:
            return None, alias_matches

        fuzzy_matches = []
        query = normalize_text(reference)
        for record in self.records:
            haystack = " ".join(
                [record.variable_id, record.variable_name, record.description, " ".join(record.aliases), " ".join(record.tags)]
            )
            if query and query in normalize_text(haystack):
                fuzzy_matches.append(record)

        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0], fuzzy_matches
        if len(fuzzy_matches) > 1:
            return None, fuzzy_matches
        return None, []


def record_from_row(row: dict[str, object]) -> VariableMetadata:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in row.items():
        key = _normalize_header(raw_key)
        canonical_key = COLUMN_ALIASES.get(key, key)
        normalized[canonical_key] = normalize_value(raw_value)

    aliases = _split_list(normalized.get("aliases", ""))
    tags = _split_list(normalized.get("tags", ""))

    return VariableMetadata(
        variable_id=normalized.get("variable_id", ""),
        variable_name=normalized.get("variable_name", ""),
        description=normalized.get("description", ""),
        variable_type=normalized.get("variable_type", ""),
        default_value=normalized.get("default_value", ""),
        source_table=normalized.get("source_table", ""),
        segment=normalized.get("segment", ""),
        model_family=normalized.get("model_family", ""),
        use_case=normalized.get("use_case", ""),
        numerator_hint=normalized.get("numerator_hint", ""),
        denominator_hint=normalized.get("denominator_hint", ""),
        owner_team=normalized.get("owner_team", ""),
        aliases=aliases,
        tags=tags,
    )


def metadata_to_dict(metadata: VariableMetadata) -> dict[str, object]:
    return asdict(metadata)


def _split_list(raw: str) -> list[str]:
    if not raw:
        return []
    values = [value.strip() for value in raw.replace("|", ",").split(",")]
    return [value for value in values if value]


def _normalize_header(value: object) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").split())
