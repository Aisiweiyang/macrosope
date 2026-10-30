"""频率转换测试：降频、流量求和、存量期末值、禁止升频。"""
from __future__ import annotations

import pandas as pd
import pytest
from macrosope.transforms.frequency import (
    resample,
    suggest_agg_method,
    validate_freq_conversion,
)


def _monthly(values, start="2023-01-01"):
    return pd.DataFrame({
        "date": pd.date_range(start, periods=len(values), freq="MS"),
        "value": values,
    })


def test_monthly_to_quarterly_sum():
    df = _monthly([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    out = resample(df, "quarterly", "sum")
    assert out["value"].tolist() == pytest.approx([6.0, 15.0])


def test_monthly_to_quarterly_mean():
    df = _monthly([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    out = resample(df, "quarterly", "mean")
    assert out["value"].tolist() == pytest.approx([2.0, 5.0])


def test_stock_last_value():
    df = _monthly([100.0, 110.0, 120.0, 130.0, 140.0, 150.0])
    out = resample(df, "quarterly", "last")
    assert out["value"].tolist() == pytest.approx([120.0, 150.0])


def test_quarterly_to_annual_sum():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=8, freq="QS"),
        "value": [1.0] * 8,
    })
    out = resample(df, "annual", "sum")
    assert out["value"].tolist() == pytest.approx([4.0, 4.0])


def test_forbid_upsampling():
    with pytest.raises(ValueError):
        validate_freq_conversion("monthly", "daily")


def test_allow_downsampling():
    validate_freq_conversion("daily", "monthly")
    validate_freq_conversion("monthly", "annual")


def test_suggest_agg_method():
    assert suggest_agg_method("flow") == "sum"
    assert suggest_agg_method("stock") == "last"
    assert suggest_agg_method("unknown", "%") == "mean"
