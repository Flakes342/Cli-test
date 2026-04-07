from __future__ import annotations

import json
import logging
from pathlib import Path

import amex_ai_agent.tools.alerts as alert_tool
from amex_ai_agent.tools.alerts import run
from amex_ai_agent.tools.base import ToolExecutionContext


CSV_TEXT = """Variable,Full Name,Description,Table,Domain,Model
RDMC3048,cmmccd48_mccd30_ratio,desc,axp-lumi.dw.wwcas_auth_analytics_02,CM Out of Pattern,XGBoost Gen 13
"""


def _context(catalog_path: Path) -> ToolExecutionContext:
    return ToolExecutionContext(logger=logging.getLogger("test"), defaults={"variable_catalog_path": str(catalog_path)})


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_alert_rationalization_uses_llm_sql_first(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)

    result = run(
        json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22", "sql_query": "SELECT 1", "execute_sql": False}),
        context=_context(catalog),
    )

    assert result["status"] == "success"
    assert result["sql_source"] == "llm_query"
    assert result["sql_query"] == "SELECT 1"


def test_alert_rationalization_fallback_sql_uses_full_name(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)

    result = run(json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22"}), context=_context(catalog))

    assert result["status"] == "success"
    assert result["sql_source"] == "fallback_template"
    assert "AVG(cmmccd48_mccd30_ratio)" in result["sql_query"]


def test_alert_rationalization_executes_sql_when_requested(monkeypatch, tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)

    def _fake_run_bq_queries(queries, logger=None):
        class _Result:
            def to_dict(self):
                return {"name": "alert_rationalization", "status": "success", "row_count": 1, "rows": [{"x": 1}], "duration_seconds": 0.01, "error": ""}

        return [_Result() for _ in queries]

    monkeypatch.setattr(alert_tool, "run_bq_queries", _fake_run_bq_queries)

    result = run(
        json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22", "execute_sql": True}),
        context=_context(catalog),
    )

    assert result["status"] == "success"
    assert result["sql_execution"]["query_results"][0]["row_count"] == 1
