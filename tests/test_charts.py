"""图表构建与可信度检查测试。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from macrosope.charts import build_figure, check_chart, prepare_series_data
from macrosope.models import ChartSpec, IndicatorMeta


def _repo_with_two_series(repo, units=("亿元", "%")):

    sids = []
    for name, unit in zip(["GDP", "CPI"], units, strict=True):
        iid = repo.create_indicator(IndicatorMeta(name=name, unit=unit, frequency="monthly"))
        sid = repo.create_series(indicator_id=iid, unit=unit, frequency="monthly")
        df = pd.DataFrame({
            "date": pd.date_range("2023-01-01", periods=6, freq="MS"),
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        })
        repo.insert_observations(sid, df)
        sids.append(sid)
    return sids


def test_build_line_figure(repo):
    sids = _repo_with_two_series(repo, units=("亿元", "亿元"))
    data = prepare_series_data(repo, sids)
    spec = ChartSpec(chart_type="line", series_ids=sids, title="测试")
    fig = build_figure(spec, data)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    assert [trace.name for trace in fig.data] == ["GDP", "CPI"]


def test_build_heatmap(repo):
    sids = _repo_with_two_series(repo, units=("亿元", "亿元"))
    data = prepare_series_data(repo, sids)
    spec = ChartSpec(chart_type="heatmap", series_ids=sids)
    fig = build_figure(spec, data)
    assert isinstance(fig, go.Figure)
    assert fig.layout.yaxis.type == "category"
    assert list(fig.data[0].y) == ["CPI", "GDP"]


def test_credibility_dual_axis_warning():
    spec = ChartSpec(chart_type="dual_axis", series_ids=[1, 2])
    report = check_chart(spec, [{"unit": "亿元"}, {"unit": "%"}])
    assert any(i.code == "dual_axis_misleading" for i in report.warnings)


def test_credibility_mixed_units_warning():
    spec = ChartSpec(chart_type="line", series_ids=[1, 2], title="x")
    report = check_chart(spec, [{"unit": "亿元"}, {"unit": "%"}])
    assert any(i.code == "mixed_units" for i in report.warnings)


def test_credibility_missing_source():
    spec = ChartSpec(chart_type="line", series_ids=[1], title="x")
    report = check_chart(spec, [{"unit": "亿元"}])
    assert any(i.code == "missing_source" for i in report.warnings)


def test_credibility_stack_incompatible_units():
    spec = ChartSpec(chart_type="stacked_bar", series_ids=[1, 2])
    report = check_chart(spec, [{"unit": "亿元"}, {"unit": "%"}])
    assert any(i.code == "stack_incompatible_units" for i in report.errors)
