"""数据质量检查测试。"""
from __future__ import annotations

import pandas as pd
from macrosope.quality import detect_frequency, run_frame_checks, run_metadata_checks


def test_empty_file():
    rep = run_frame_checks(pd.DataFrame())
    assert rep.has_errors
    assert any(i.code == "empty_file" for i in rep.errors)


def test_empty_column():
    df = pd.DataFrame({"a": [1, 2], "b": [None, None]})
    rep = run_frame_checks(df)
    assert any(i.code == "empty_column" for i in rep.errors)


def test_duplicate_columns():
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    rep = run_frame_checks(df)
    assert any(i.code == "duplicate_columns" for i in rep.errors)


def test_duplicate_dates():
    df = pd.DataFrame({"date": ["2023-01", "2023-01"], "value": [1.0, 2.0]})
    rep = run_frame_checks(df, date_col="date", value_col="value")
    assert any(i.code == "duplicate_dates" for i in rep.errors)


def test_unparseable_dates():
    df = pd.DataFrame({"date": ["2023-01", "not-a-date"], "value": [1.0, 2.0]})
    rep = run_frame_checks(df, date_col="date")
    assert any(i.code == "unparseable_dates" for i in rep.errors)


def test_missing_values_warning():
    df = pd.DataFrame({"date": ["2023-01", "2023-02"], "value": [1.0, None]})
    rep = run_frame_checks(df, date_col="date", value_col="value")
    assert any(i.code == "missing_values" for i in rep.warnings)


def test_non_numeric_values():
    df = pd.DataFrame({"date": ["2023-01", "2023-02"], "value": ["1.0", "abc"]})
    rep = run_frame_checks(df, date_col="date", value_col="value")
    assert any(i.code == "non_numeric_values" for i in rep.errors)


def test_outliers_detected():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=10, freq="MS"),
        "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1000.0],
    })
    rep = run_frame_checks(df, date_col="date", value_col="value")
    assert any(i.code == "outliers" for i in rep.warnings)


def test_metadata_mixed_units_warning():
    metas = [
        {"name": "GDP", "unit": "亿元", "currency": "CNY", "frequency": "monthly"},
        {"name": "CPI", "unit": "%", "currency": "CNY", "frequency": "monthly"},
    ]
    rep = run_metadata_checks(metas)
    assert any(i.code == "mixed_units" for i in rep.warnings)


def test_metadata_mixed_currencies_warning():
    metas = [
        {"name": "A", "unit": "亿元", "currency": "CNY"},
        {"name": "B", "unit": "亿元", "currency": "USD"},
    ]
    rep = run_metadata_checks(metas)
    assert any(i.code == "mixed_currencies" for i in rep.warnings)


def test_metadata_percent_decimal_mixed():
    metas = [
        {"name": "A", "unit": "%"},
        {"name": "B", "unit": "亿元"},
    ]
    rep = run_metadata_checks(metas)
    assert any(i.code == "mixed_percent_decimal" for i in rep.warnings)


def test_detect_frequency():
    monthly = pd.date_range("2023-01-01", periods=12, freq="MS")
    freq, regular = detect_frequency(monthly)
    assert freq == "monthly"
    assert regular
