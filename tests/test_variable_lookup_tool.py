from __future__ import annotations

import json
import logging
from pathlib import Path

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.parser import ToolCall
from amex_ai_agent.tools.base import ToolExecutionContext
from amex_ai_agent.tools.variable_lookup import run


CSV_TEXT = """Variable,Full Name,Description,Table,Domain,Model
var_auth_amt,Authorization Amount,Authorized amount in USD,feature_store,authorization,rnn
CMN5,Common Merchant 5,Common merchant mismatch score,feature_store,authentication,rnn
var_auth_rate,Authorization Rate,Rate of authorizations over time,feature_store,authorization,rnn
var_device_risk,Device Risk Score,Risk score for device fingerprint,model_features,risk,xgboost
"""


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def _context(catalog_path: Path) -> ToolExecutionContext:
    return ToolExecutionContext(logger=logging.getLogger("test"), defaults={"variable_catalog_path": str(catalog_path)})


def test_variable_lookup_tool_returns_exact_match(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)

    result = run(json.dumps({"code": "CMN5"}), context=_context(catalog_path))

    assert result["status"] == "success"
    assert result["match_type"] == "exact"
    assert result["record"]["variable"] == "CMN5"


def test_variable_lookup_tool_falls_back_to_fuzzy_match_when_code_is_partial(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)

    result = run(json.dumps({"code": "cmn"}), context=_context(catalog_path))

    assert result["status"] == "success"
    assert result["match_type"] == "fuzzy"
    assert result["total_matches"] == 1
    assert result["results"][0]["variable"] == "CMN5"


def test_variable_lookup_tool_accepts_raw_string_query_and_returns_single_best_match(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)

    result = run("cmn5", context=_context(catalog_path))

    assert result["status"] == "success"
    assert result["match_type"] == "fuzzy"
    assert result["result_count"] == 1
    assert result["total_matches"] == 1
    assert result["results"][0]["variable"] == "CMN5"


def test_variable_lookup_tool_returns_ambiguous_fuzzy_results_with_default_single_output(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)

    result = run(json.dumps({"query": "authorization", "model": "rnn"}), context=_context(catalog_path))

    assert result["status"] == "ambiguous"
    assert result["match_type"] == "fuzzy"
    assert result["result_count"] == 1
    assert result["total_matches"] == 2


def test_variable_lookup_tool_can_filter_without_search_text(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)

    result = run(json.dumps({"domain": "risk"}), context=_context(catalog_path))

    assert result["status"] == "success"
    assert result["match_type"] == "filtered_list"
    assert result["results"][0]["variable"] == "var_device_risk"


def test_variable_lookup_tool_requires_search_terms_or_filters(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)

    result = run("", context=_context(catalog_path))

    assert result["status"] == "needs_user_input"


def test_executor_runs_variable_lookup_tool(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)
    config = AgentConfig(variable_catalog_path=str(catalog_path))
    executor = ToolExecutor(config)

    results = executor.execute([ToolCall(name="variable_lookup", argument="cmn5")])

    assert len(results) == 1
    assert results[0].status == "success"
    payload = json.loads(results[0].output)
    assert payload["results"][0]["variable"] == "CMN5"
