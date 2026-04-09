from __future__ import annotations

from pathlib import Path

from amex_ai_agent.variable_catalog import VariableCatalog


CSV_TEXT = """Variable,Full Name,Description,Variable Type,Default Value,Table,Domain,Model
var_auth_amt,Authorization Amount,Authorized amount in USD,Numerical,0,feature_store,authorization,rnn
var_auth_cnt,Authorization Count,Number of authorizations,Numerical,,feature_store,authorization,xgboost
var_fraud_flag,Fraud Flag,Predicted fraud indicator,Categorical,@,model_features,risk,rnn
"""


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_catalog_loading_normalizes_headers_and_values(tmp_path: Path) -> None:
    catalog = VariableCatalog.from_csv(_write_catalog(tmp_path))

    assert len(catalog.records) == 3
    first = catalog.records[0]
    assert first.variable == "var_auth_amt"
    assert first.full_name == "Authorization Amount"
    assert first.description == "Authorized amount in USD"
    assert first.variable_type == "Numerical"
    assert first.default_value == "0"
    assert first.table == "feature_store"
    assert first.domain == "authorization"
    assert first.model == "rnn"


def test_exact_variable_lookup_is_case_and_symbol_insensitive(tmp_path: Path) -> None:
    catalog = VariableCatalog.from_csv(_write_catalog(tmp_path))

    record = catalog.exact_lookup("VAR_AUTH_AMT")

    assert record is not None
    assert record.variable == "var_auth_amt"


def test_fuzzy_search_matches_code_full_name_and_description(tmp_path: Path) -> None:
    catalog = VariableCatalog.from_csv(_write_catalog(tmp_path))

    results = catalog.search("authorized usd amount", limit=5)

    assert results
    assert results[0].variable == "var_auth_amt"


def test_model_and_domain_filters_return_scoped_records(tmp_path: Path) -> None:
    catalog = VariableCatalog.from_csv(_write_catalog(tmp_path))

    rnn_records = catalog.filter_records(model="RNN")
    authorization_records = catalog.filter_records(domain="authorization")

    assert {record.variable for record in rnn_records} == {"var_auth_amt", "var_fraud_flag"}
    assert {record.variable for record in authorization_records} == {"var_auth_amt", "var_auth_cnt"}
