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
