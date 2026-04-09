from __future__ import annotations

import json
import logging
from pathlib import Path

import amex_ai_agent.tools.alerts as alert_tool
from amex_ai_agent.tools.alerts import run
from amex_ai_agent.tools.base import ToolExecutionContext


CSV_TEXT = """Variable,Full Name,Description,Variable Type,Default Value,Table,Domain,Model
RDMC3048,cmmccd48_mccd30_ratio,desc,Numerical,0,axp-lumi.dw.wwcas_auth_analytics_02,CM Out of Pattern,XGBoost Gen 13
AAVMDLCD,aav_model_rslt_cd,desc,Categorical,@,axp-lumi.dw.wwcas_auth_analytics_01,Authentication,XGBoost Gen 13
"""


def _context(catalog_path: Path) -> ToolExecutionContext:
    return ToolExecutionContext(
        logger=logging.getLogger("test"),
        defaults={
            "variable_catalog_path": str(catalog_path),
            "default_project_id": "prj",
            "default_dataset_id": "ds",
            "default_folder_nm": "alerts",
        },
    )


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_alert_rationalization_builds_default_query_set_by_variable_type(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)

    result = run(
        json.dumps({"variable_id": "AAVMDLCD", "alert_date": "2026-03-22", "alerted_value": "A"}),
        context=_context(catalog),
    )

    assert result["status"] == "success"
    query_names = [item["name"] for item in result["sql_execution"]["query_set"]]
    assert query_names == ["00_cat_var_dist", "01_cat_var_stats", "02_cat_top_cm", "02_cat_top_se"]
    assert result["needs_llm_followup"] is True


def test_alert_rationalization_uses_default_aware_numerical_stats_query(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)

    result = run(json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22"}), context=_context(catalog))

    assert result["status"] == "success"
    query_names = [item["name"] for item in result["sql_execution"]["query_set"]]
    assert query_names == ["00_num_var_dist", "01_num_var_stats_w_default", "02_num_top_cm", "02_num_top_se"]
    first_sql = result["sql_execution"]["query_set"][0]["sql"]
    assert "LEFT JOIN `axp-lumi.dw.wwcas_auth_analytics_02` b" in first_sql


def test_alert_rationalization_executes_sql_when_requested(monkeypatch, tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    calls: list[tuple[str, str]] = []

    def _fake_run_bq_query(sql, *, name="query", logger=None, destination_table=""):
        calls.append((name, destination_table))

        class _Result:
            def to_dict(self):
                return {
                    "name": name,
                    "status": "success",
                    "row_count": 7,
                    "rows": [{"x": 1}],
                    "duration_seconds": 0.01,
                    "error": "",
                    "destination_table": destination_table,
                }

        return _Result()

    monkeypatch.setattr(alert_tool, "run_bq_query", _fake_run_bq_query)

    result = run(
        json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22", "execute_sql": True}),
        context=_context(catalog),
    )

    assert result["status"] == "success"
    assert len(result["sql_execution"]["query_results"]) == 4
    assert result["sql_execution"]["query_results"][0]["row_count"] == 7
    assert result["sql_execution"]["destination_tables"]
    assert result["sql_execution"]["persist_query_tables"] is True
    assert len(calls) == 4
    assert result["needs_llm_followup"] is False


def test_alert_rationalization_requires_valid_variable_name(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)

    result = run(
        json.dumps({"variable_id": "RDMC3048", "variable_name": "@@@", "alert_date": "2026-03-22"}),
        context=_context(catalog),
    )

    assert result["status"] == "needs_user_input"
    assert "Variable name is empty/invalid" in result["message"]


def test_alert_rationalization_requires_dataset_for_table_persistence(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    context = ToolExecutionContext(logger=logging.getLogger("test"), defaults={"variable_catalog_path": str(catalog)})

    result = run(
        json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22", "execute_sql": True}),
        context=context,
    )

    assert result["status"] == "needs_user_input"
    assert "project_id and dataset_id are required" in result["message"]


def test_alert_rationalization_normalizes_fully_qualified_project_and_dataset(monkeypatch, tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    captured_destinations: list[str] = []
    context = ToolExecutionContext(
        logger=logging.getLogger("test"),
        defaults={
            "variable_catalog_path": str(catalog),
            "default_project_id": "prj-p-ai-fraud.atanw9",
            "default_dataset_id": "prj-p-ai-fraud.atanw9",
        },
    )

    def _fake_run_bq_query(sql, *, name="query", logger=None, destination_table=""):
        captured_destinations.append(destination_table)

        class _Result:
            def to_dict(self):
                return {
                    "name": name,
                    "status": "success",
                    "row_count": 1,
                    "rows": [{"x": 1}],
                    "duration_seconds": 0.01,
                    "error": "",
                    "destination_table": destination_table,
                }

        return _Result()

    monkeypatch.setattr(alert_tool, "run_bq_query", _fake_run_bq_query)

    result = run(
        json.dumps({"variable_id": "RDMC3048", "alert_date": "2026-03-22", "execute_sql": True}),
        context=context,
    )

    assert result["status"] == "success"
    assert captured_destinations
    assert captured_destinations[0].startswith("prj-p-ai-fraud.atanw9.")
