from __future__ import annotations

import json
import logging
from pathlib import Path

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.parser import ToolCall
from amex_ai_agent.tools.base import ToolExecutionContext
import amex_ai_agent.tools.rca_analysis as rca_tool
from amex_ai_agent.tools.rca_analysis import run


CSV_TEXT = """Variable,Full Name,Description,Table,Domain,Model,Aliases,Variable Type,Numerator Hint,Denominator Hint
RDMC3048,cmmccd48_mccd30_ratio,Ratio of amount of approved charges by CM15 in last 48 hours in incoming MCC code to amount in incoming MCC over last 30-396 days,axp-lumi.dw.wwcas_auth_analytics_02,CM Out of Pattern,"XGBoost Gen 13, Canceled Plastic","rdmc_3048|mccd ratio",ratio,approved_amt_48h,mcc_amt_30_396
"""


def _catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def _context(catalog_path: Path) -> ToolExecutionContext:
    return ToolExecutionContext(logger=logging.getLogger("test"), defaults={"variable_catalog_path": str(catalog_path)})


def test_rca_analysis_tool_parses_natural_language_input(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)

    result = run(json.dumps({"user_query": "RDMC3048 got a lower-limit alert on 2026-03-22"}), context=_context(catalog))

    assert result["status"] == "success"
    assert result["input_context"]["resolved_variable_id"] == "RDMC3048"
    assert result["input_context"]["alert_type"] == "lower_limit_breach"


def test_rca_analysis_tool_supports_structured_mode(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)

    result = run(
        json.dumps(
            {
                "variable_id": "RDMC3048",
                "alert_date": "2026-03-22",
                "alert_type": "lower_limit_breach",
                "observations": {"metric_value": 0.1, "baseline_value": 0.2},
            }
        ),
        context=_context(catalog),
    )

    assert result["status"] == "success"
    assert result["analysis_window"]["end_date"] == "2026-03-22"


def test_executor_runs_rca_analysis_tool(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    executor = ToolExecutor(AgentConfig(variable_catalog_path=str(catalog)))

    results = executor.execute([ToolCall(name="rca_analysis", argument=json.dumps({"user_query": "RCA for RDMC3048 yesterday lower limit"}))])

    assert len(results) == 1
    assert results[0].status == "success"
    payload = json.loads(results[0].output)
    assert payload["input_context"]["resolved_variable_id"] == "RDMC3048"


def test_rca_analysis_tool_executes_supplied_query(monkeypatch, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)

    def _fake_run_bq_queries(queries, logger=None):
        class _Result:
            def __init__(self, name, rows):
                self._name = name
                self._rows = rows

            def to_dict(self):
                return {
                    "name": self._name,
                    "status": "success",
                    "row_count": len(self._rows),
                    "rows": self._rows,
                    "duration_seconds": 0.01,
                    "error": "",
                }

        return [_Result(name, [{"k": 1}]) for name, _ in queries]

    monkeypatch.setattr(rca_tool, "run_bq_queries", _fake_run_bq_queries)

    result = run(
        json.dumps(
            {
                "user_query": "RDMC3048 got a lower-limit alert on 2026-03-22",
                "execute_sql": True,
                "query": "select 1 as k",
            }
        ),
        context=_context(catalog),
    )

    assert result["status"] == "success"
    assert result["sql_execution"]["query_results"]
    assert result["sql_execution"]["query_results"][0]["row_count"] == 1
