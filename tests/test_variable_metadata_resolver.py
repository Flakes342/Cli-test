from __future__ import annotations

from pathlib import Path

from amex_ai_agent.rca.variable_metadata_resolver import VariableMetadataResolver


CSV_TEXT = """Variable,Full Name,Description,Table,Domain,Model,Aliases,Variable Type,Numerator Hint,Denominator Hint,Owner Team,Tags
RDMC3048,cmmccd48_mccd30_ratio,Ratio of amount of approved charges by CM15 in last 48 hours in incoming MCC code to amount in incoming MCC over last 30-396 days,axp-lumi.dw.wwcas_auth_analytics_02,CM Out of Pattern,"XGBoost Gen 13, Canceled Plastic","rdmc_3048|mccd ratio",ratio,approved_amt_48h,mcc_amt_30_396,cdt-analytics,"cdit,control-chart"
AAVN_D48,addr_ver_an_48h_amt,Total dollar amount,axp-lumi.dw.wwcas_authorization,Authentication,XGBoost Gen 13,,count,,,
"""


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_resolver_exact_and_alias_resolution(tmp_path: Path) -> None:
    resolver = VariableMetadataResolver.from_csv(_write_catalog(tmp_path))

    direct, _ = resolver.resolve("RDMC3048")
    alias, _ = resolver.resolve("mccd ratio")

    assert direct is not None
    assert alias is not None
    assert direct.variable_name == "cmmccd48_mccd30_ratio"
    assert alias.variable_id == "RDMC3048"


def test_resolver_ambiguous_on_partial_name(tmp_path: Path) -> None:
    resolver = VariableMetadataResolver.from_csv(_write_catalog(tmp_path))

    resolved, candidates = resolver.resolve("amount")

    assert resolved is None
    assert len(candidates) >= 2
