from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


CANONICAL_FIELD_NAMES = {
    "variable": "variable",
    "full name": "full_name",
    "description": "description",
    "variable type": "variable_type",
    "default value": "default_value",
    "table": "table",
    "domain": "domain",
    "model": "model",
}

SEARCHABLE_FIELDS = ("variable", "full_name", "description")


@dataclass(frozen=True)
class VariableRecord:
    variable: str
    full_name: str = ""
    description: str = ""
    variable_type: str = ""
    default_value: str = ""
    table: str = ""
    domain: str = ""
    model: str = ""

    @property
    def normalized_variable(self) -> str:
        return normalize_token(self.variable)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class VariableCatalog:
    def __init__(self, records: Iterable[VariableRecord], source_path: str | Path | None = None) -> None:
        self.records = list(records)
        self.source_path = str(source_path or "")
        self._by_variable = {record.normalized_variable: record for record in self.records if record.normalized_variable}

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> "VariableCatalog":
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        records = [record_from_row(row) for row in rows if row]
        return cls(records, source_path=path)

    def exact_lookup(self, variable_code: str) -> VariableRecord | None:
        return self._by_variable.get(normalize_token(variable_code))

    def filter_records(
        self,
        *,
        model: str | None = None,
        domain: str | None = None,
        table: str | None = None,
    ) -> list[VariableRecord]:
        normalized_filters = {
            "model": normalize_token(model),
            "domain": normalize_token(domain),
            "table": normalize_token(table),
        }

        matches: list[VariableRecord] = []
        for record in self.records:
            if normalized_filters["model"] and normalize_token(record.model) != normalized_filters["model"]:
                continue
            if normalized_filters["domain"] and normalize_token(record.domain) != normalized_filters["domain"]:
                continue
            if normalized_filters["table"] and normalize_token(record.table) != normalized_filters["table"]:
                continue
            matches.append(record)
        return matches

    def search(
        self,
        text: str,
        *,
        model: str | None = None,
        domain: str | None = None,
        table: str | None = None,
        limit: int | None = 10,
    ) -> list[VariableRecord]:
        query = normalize_text(text)
        if not query:
            records = self.filter_records(model=model, domain=domain, table=table)
            return records if limit is None else records[: max(limit, 0)]

        scoped_records = self.filter_records(model=model, domain=domain, table=table)
        scored: list[tuple[float, VariableRecord]] = []
        for record in scoped_records:
            score = max(self._score_field(query, getattr(record, field, "")) for field in SEARCHABLE_FIELDS)
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda item: (-item[0], item[1].variable.lower()))
        ranked = [record for _, record in scored]
        return ranked if limit is None else ranked[: max(limit, 0)]

    @staticmethod
    def _score_field(query: str, raw_value: str) -> float:
        value = normalize_text(raw_value)
        if not value:
            return 0.0
        if query == value:
            return 1.0
        if query in value:
            return min(0.99, 0.7 + (len(query) / max(len(value), 1)) * 0.3)

        query_tokens = set(query.split())
        value_tokens = set(value.split())
        overlap = len(query_tokens & value_tokens)
        token_score = overlap / max(len(query_tokens), 1)
        similarity = SequenceMatcher(None, query, value).ratio()
        return max(token_score * 0.85, similarity * 0.75) if max(token_score, similarity) >= 0.4 else 0.0


def load_variable_catalog(csv_path: str | Path) -> VariableCatalog:
    return VariableCatalog.from_csv(csv_path)


def record_from_row(row: dict[str, object]) -> VariableRecord:
    normalized_row = {normalize_header(key): value for key, value in row.items()}
    return VariableRecord(
        variable=normalize_value(normalized_row.get("variable", "")),
        full_name=normalize_value(normalized_row.get("full_name", "")),
        description=normalize_value(normalized_row.get("description", "")),
        variable_type=normalize_value(normalized_row.get("variable_type", "")),
        default_value=normalize_value(normalized_row.get("default_value", "")),
        table=normalize_value(normalized_row.get("table", "")),
        domain=normalize_value(normalized_row.get("domain", "")),
        model=normalize_value(normalized_row.get("model", "")),
    )


def normalize_header(value: object) -> str:
    text = " ".join(str(value or "").replace("_", " ").replace("-", " ").split()).strip().lower()
    return CANONICAL_FIELD_NAMES.get(text, text.replace(" ", "_"))


def normalize_value(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_token(value: object) -> str:
    return "".join(ch for ch in normalize_value(value).lower() if ch.isalnum())


def normalize_text(value: object) -> str:
    cleaned = []
    for ch in normalize_value(value).lower():
        cleaned.append(ch if ch.isalnum() else " ")
    return " ".join("".join(cleaned).split())
