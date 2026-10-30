"""字段映射与宽长表转换测试。"""
from __future__ import annotations

import pandas as pd
from macrosope.mapping import detect_layout, suggest_roles, to_long, to_wide


def test_suggest_roles_dates_and_values():
    df = pd.DataFrame({
        "日期": ["2023-01", "2023-02"],
        "GDP": [100.0, 101.0],
        "备注": ["a", "b"],
    })
    roles = suggest_roles(df)
    assert roles["日期"] == "date"
    assert roles["GDP"] == "value"


def test_detect_layout():
    assert detect_layout({"日期": "date", "GDP": "value", "CPI": "value"}) == "wide"
    assert detect_layout({"日期": "date", "指标": "indicator", "数值": "value"}) == "long"


def test_wide_to_long():
    df = pd.DataFrame({
        "日期": ["2023-01", "2023-02"],
        "GDP": [100.0, 101.0],
        "CPI": [2.0, 2.1],
    })
    roles = {"日期": "date", "GDP": "value", "CPI": "value"}
    long = to_long(df, roles)
    assert set(long.columns) >= {"date", "indicator", "value"}
    assert len(long) == 4  # 2 指标 × 2 期
    assert set(long["indicator"]) == {"GDP", "CPI"}


def test_long_to_wide():
    long = pd.DataFrame({
        "date": ["2023-01", "2023-01", "2023-02", "2023-02"],
        "indicator": ["GDP", "CPI", "GDP", "CPI"],
        "value": [100.0, 2.0, 101.0, 2.1],
    })
    roles = {"date": "date", "indicator": "indicator", "value": "value"}
    wide = to_wide(long, roles)
    assert set(wide.columns) == {"date", "GDP", "CPI"}
    assert wide.loc[wide["date"] == "2023-01", "GDP"].iloc[0] == 100.0


def test_wide_to_long_with_entity():
    df = pd.DataFrame({
        "日期": ["2023-01", "2023-01"],
        "地区": ["北京", "上海"],
        "GDP": [100.0, 90.0],
    })
    roles = {"日期": "date", "地区": "entity", "GDP": "value"}
    long = to_long(df, roles)
    assert "entity" in long.columns
    assert set(long["entity"]) == {"北京", "上海"}
