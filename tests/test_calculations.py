"""经济数据计算测试：同比、环比、年化、指数化、移动平均、累计转当期等。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from macrosope.transforms import calculations as calc


def test_yoy(monthly_df):
    out = calc.yoy(monthly_df, freq="monthly")
    # 前 12 期为 NaN，第 13 期 = (112/100 - 1)*100 = 12%
    assert pd.isna(out["value"].iloc[0])
    assert out["value"].iloc[12] == pytest.approx(12.0)


def test_mom(monthly_df):
    out = calc.mom(monthly_df)
    # 第 2 期环比 = (101/100 - 1)*100 = 1%
    assert out["value"].iloc[1] == pytest.approx(1.0)
    assert pd.isna(out["value"].iloc[0])


def test_annualized_mom(monthly_df):
    # 用恒定 1% 月环比数据
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=13, freq="MS"),
        "value": [100 * (1.01 ** i) for i in range(13)],
    })
    out = calc.annualized_mom(df, periods_per_year=12)
    # (1.01^12 - 1)*100 ≈ 12.68%
    assert out["value"].iloc[1] == pytest.approx(((1.01 ** 12) - 1) * 100, rel=1e-6)


def test_cumulative_to_period(monthly_df):
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [10.0, 25.0, 45.0],  # 累计值
    })
    out = calc.cumulative_to_period(df)
    assert pd.isna(out["value"].iloc[0])
    assert out["value"].iloc[1] == pytest.approx(15.0)
    assert out["value"].iloc[2] == pytest.approx(20.0)


def test_period_to_cumulative():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [10.0, 15.0, 20.0],
    })
    out = calc.period_to_cumulative(df)
    assert out["value"].tolist() == pytest.approx([10.0, 25.0, 45.0])


def test_index_first(monthly_df):
    out = calc.index_first(monthly_df)
    assert out["value"].iloc[0] == pytest.approx(100.0)
    assert out["value"].iloc[1] == pytest.approx(101.0 / 100.0 * 100)


def test_index_to_date(monthly_df):
    out = calc.index_to_date(monthly_df, "2023-02-01")
    # 基期 2023-02 = 101 -> 100；首期 100 -> 100/101*100
    assert out["value"].iloc[1] == pytest.approx(100.0)
    assert out["value"].iloc[0] == pytest.approx(100 / 101 * 100)


def test_index_year_avg(monthly_df):
    out = calc.index_year_avg(monthly_df, 2023)
    # 2023 年均值 = (100..111) 平均 = 105.5
    mean = np.mean(np.arange(100, 112))
    assert out["value"].iloc[0] == pytest.approx(100 / mean * 100)


def test_moving_average(monthly_df):
    out = calc.moving_average(monthly_df, window=3)
    assert pd.isna(out["value"].iloc[0])
    assert out["value"].iloc[2] == pytest.approx((100 + 101 + 102) / 3)


def test_moving_median():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [100.0, 1000.0, 101.0],
    })
    out = calc.moving_median(df, window=3)
    assert out["value"].iloc[2] == pytest.approx(101.0)


def test_log_diff():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [100.0, 110.0, 121.0],
    })
    out = calc.log_diff(df, scale=100)
    assert out["value"].iloc[1] == pytest.approx(np.log(110 / 100) * 100)


def test_zscore(monthly_df):
    out = calc.zscore(monthly_df)
    assert out["value"].mean() == pytest.approx(0.0, abs=1e-9)
    assert out["value"].std() == pytest.approx(1.0, rel=1e-6)


def test_minmax(monthly_df):
    out = calc.minmax(monthly_df)
    assert out["value"].min() == pytest.approx(0.0)
    assert out["value"].max() == pytest.approx(1.0)


def test_percentile_rank(monthly_df):
    out = calc.percentile_rank(monthly_df)
    assert out["value"].max() == pytest.approx(100.0)
    assert out["value"].min() == pytest.approx(100.0 / len(monthly_df))


def test_share():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [10.0, 30.0, 60.0],
    })
    out = calc.share(df)
    assert out["value"].tolist() == pytest.approx([10.0, 30.0, 60.0])


def test_structure_change():
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [10.0, 12.0, 15.0],
    })
    out = calc.structure_change(df)
    assert out["value"].iloc[1] == pytest.approx(2.0)


def test_per_capita_denominator_zero():
    value = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [100.0, 100.0, 100.0],
    })
    pop = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [0.0, 50.0, 100.0],  # 第一期为 0，应得 inf 而非崩溃
    })
    out = calc.per_capita(value, pop)
    assert np.isinf(out["value"].iloc[0])
    assert out["value"].iloc[1] == pytest.approx(2.0)


def test_nominal_to_real():
    nominal = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=2, freq="MS"),
        "value": [200.0, 200.0],
    })
    deflator = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=2, freq="MS"),
        "value": [100.0, 200.0],
    })
    out = calc.nominal_to_real(nominal, deflator)
    assert out["value"].iloc[0] == pytest.approx(200.0)
    assert out["value"].iloc[1] == pytest.approx(100.0)


def test_correlation():
    a = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=5, freq="MS"),
        "value": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    b = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=5, freq="MS"),
        "value": [2.0, 4.0, 6.0, 8.0, 10.0],
    })
    assert calc.correlation(a, b) == pytest.approx(1.0)


def test_lag_correlation():
    a = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=10, freq="MS"),
        "value": np.arange(10, dtype=float),
    })
    b = a.copy()
    out = calc.lag_correlation(a, b, max_lag=2)
    assert out["correlation"].iloc[0] == pytest.approx(1.0)
    assert len(out) == 3
