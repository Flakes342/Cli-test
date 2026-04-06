from __future__ import annotations

from amex_ai_agent.rca.sql_templates import render_driver_sql, render_stage_funnel_sql


def test_render_stage_funnel_sql_includes_date_and_stage_names() -> None:
    sql = render_stage_funnel_sql(start_date="2026-03-20", end_date="2026-03-22", sample_rate=0.025)

    assert "2026-03-20" in sql
    assert "2026-03-22" in sql
    assert "with_zva" in sql
    assert "noncanc" in sql


def test_render_driver_sql_dimension_mapping() -> None:
    sql = render_driver_sql(start_date="2026-03-20", end_date="2026-03-22", dimension="mcc")

    assert "cm11" in sql
    assert "GROUP BY 1" in sql
