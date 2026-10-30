"""清洗变换测试。"""
from __future__ import annotations

import pandas as pd
import pytest
from macrosope.transforms.cleaning import (
    drop_duplicates,
    fill_missing,
    manual_edit,
    sort_by_date,
    unit_convert,
)


def test_sort_by_date():
    df = pd.DataFrame({
        "date": ["2023-03-01", "2023-01-01", "2023-02-01"],
        "value": [3.0, 1.0, 2.0],
    })
    out = sort_by_date(df)
    assert out["value"].tolist() == [1.0, 2.0, 3.0]


def test_drop_duplicates():
    df = pd.DataFrame({
        "date": ["2023-01-01", "2023-01-01", "2023-02-01"],
        "value": [1.0, 99.0, 2.0],
    })
    out = drop_duplicates(df)
    assert len(out) == 2
    assert out["value"].iloc[0] == 1.0  # 保留首个


def test_unit_convert():
    df = pd.DataFrame({"date": ["2023-01-01"], "value": [100.0]})
    out = unit_convert(df, 0.0001)
    assert out["value"].iloc[0] == pytest.approx(0.01)


def test_fill_missing_keep():
    df = pd.DataFrame({
        "date": ["2023-01-01", "2023-02-01"],
        "value": [1.0, None],
    })
    out = fill_missing(df, "keep")
    assert out["value"].isna().sum() == 1


def test_fill_missing_drop():
    df = pd.DataFrame({
        "date": ["2023-01-01", "2023-02-01"],
        "value": [1.0, None],
    })
    out = fill_missing(df, "drop")
    assert len(out) == 1


def test_fill_missing_ffill():
    df = pd.DataFrame({
        "date": ["2023-01-01", "2023-02-01", "2023-03-01"],
        "value": [1.0, None, None],
    })
    out = fill_missing(df, "ffill")
    assert out["value"].tolist() == [1.0, 1.0, 1.0]


def test_fill_missing_interp():
    df = pd.DataFrame({
        "date": ["2023-01-01", "2023-02-01", "2023-03-01"],
        "value": [1.0, None, 3.0],
    })
    out = fill_missing(df, "interp")
    assert out["value"].iloc[1] == pytest.approx(2.0)


def test_fill_missing_invalid():
    with pytest.raises(ValueError):
        fill_missing(pd.DataFrame({"date": [], "value": []}), "bogus")


def test_manual_edit():
    df = pd.DataFrame({
        "date": ["2023-01-01", "2023-02-01"],
        "value": [1.0, 2.0],
    })
    out = manual_edit(df, [{"date": "2023-02-01", "value": 99.0}])
    assert out["value"].iloc[1] == 99.0
