"""经济数据计算。

所有计算函数输入输出均为单序列 DataFrame（列：date、value），
缺失值一律保留为 NaN，不静默填充。增长率类输出单位为百分数（已 ×100）。
相关分析（correlation / lag_correlation）为独立分析函数，返回标量或表，
不进入序列管道。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 频率 -> 一年对应的期数（用于同比 shift）
_FREQ_PERIODS = {"daily": 365, "weekly": 52, "monthly": 12, "quarterly": 4, "annual": 1}
# 频率 -> 一个季度对应的期数
_QUARTER_PERIODS = {"daily": 90, "weekly": 13, "monthly": 3, "quarterly": 1, "annual": 1}


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return out


def _align(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """按日期对齐两条序列（内连接），返回各自仍以 value 命名的列。"""
    aa = _sorted(a).rename(columns={"value": "value_a"})
    bb = _sorted(b).rename(columns={"value": "value_b"})
    m = pd.merge(aa, bb, on="date", how="inner")
    return (
        m[["date", "value_a"]].rename(columns={"value_a": "value"}),
        m[["date", "value_b"]].rename(columns={"value_b": "value"}),
    )


# ------------------------------------------------------------------ 增长率
def yoy(df: pd.DataFrame, freq: str = "monthly") -> pd.DataFrame:
    """同比增长率（%）。"""
    d = _sorted(df)
    n = _FREQ_PERIODS.get(freq, 12)
    out = d.copy()
    out["value"] = d["value"].pct_change(n) * 100
    return out[["date", "value"]]


def mom(df: pd.DataFrame) -> pd.DataFrame:
    """环比增长率（%）。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].pct_change(1) * 100
    return out[["date", "value"]]


def annualized_mom(df: pd.DataFrame, periods_per_year: int = 12) -> pd.DataFrame:
    """年化环比（%）：(1+mom)^periods_per_year - 1。"""
    d = _sorted(df)
    mom_rate = d["value"].pct_change(1)
    out = d.copy()
    out["value"] = ((1 + mom_rate) ** periods_per_year - 1) * 100
    return out[["date", "value"]]


def period_change(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    """指定期变化率（%）：(value_t / value_{t-periods} - 1) × 100。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].pct_change(periods) * 100
    return out[["date", "value"]]


def log_diff(df: pd.DataFrame, scale: float = 100.0) -> pd.DataFrame:
    """对数差分：scale × (ln(value_t) - ln(value_{t-1}))。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = np.log(d["value"]).diff() * scale
    return out[["date", "value"]]


# ------------------------------------------------------------------ 累计/当期
def cumulative_to_period(df: pd.DataFrame) -> pd.DataFrame:
    """累计值转当期值：value_t - value_{t-1}。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].diff()
    return out[["date", "value"]]


def period_to_cumulative(df: pd.DataFrame) -> pd.DataFrame:
    """当期值转累计值：滚动累加（按年）。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].cumsum()
    return out[["date", "value"]]


# ------------------------------------------------------------------ 指数化
def _index_base(df: pd.DataFrame, base_value: float) -> pd.DataFrame:
    out = df.copy()
    out["value"] = df["value"] / base_value * 100
    return out[["date", "value"]]


def index_to_date(df: pd.DataFrame, base_date: str) -> pd.DataFrame:
    """指定日期 = 100。"""
    d = _sorted(df)
    base_date = pd.to_datetime(base_date)
    rows = d[d["date"] == base_date]
    if rows.empty:
        raise ValueError(f"基期日期 {base_date} 不在序列中")
    return _index_base(d, float(rows["value"].iloc[0]))


def index_first(df: pd.DataFrame) -> pd.DataFrame:
    """首期 = 100。"""
    d = _sorted(df)
    return _index_base(d, float(d["value"].iloc[0]))


def index_year_avg(df: pd.DataFrame, base_year: int) -> pd.DataFrame:
    """指定年度平均值 = 100。"""
    d = _sorted(df)
    d["year"] = d["date"].dt.year
    base_mean = d[d["year"] == base_year]["value"].mean()
    if pd.isna(base_mean):
        raise ValueError(f"基期年度 {base_year} 无数据")
    out = d.copy()
    out["value"] = d["value"] / base_mean * 100
    return out[["date", "value"]]


# ------------------------------------------------------------------ 移动统计
def moving_average(df: pd.DataFrame, window: int) -> pd.DataFrame:
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].rolling(window).mean()
    return out[["date", "value"]]


def moving_median(df: pd.DataFrame, window: int) -> pd.DataFrame:
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].rolling(window).median()
    return out[["date", "value"]]


def rolling_volatility(df: pd.DataFrame, window: int) -> pd.DataFrame:
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].rolling(window).std()
    return out[["date", "value"]]


# ------------------------------------------------------------------ 标准化
def zscore(df: pd.DataFrame) -> pd.DataFrame:
    d = _sorted(df)
    out = d.copy()
    out["value"] = (d["value"] - d["value"].mean()) / d["value"].std()
    return out[["date", "value"]]


def minmax(df: pd.DataFrame) -> pd.DataFrame:
    d = _sorted(df)
    out = d.copy()
    vmin, vmax = d["value"].min(), d["value"].max()
    out["value"] = (d["value"] - vmin) / (vmax - vmin)
    return out[["date", "value"]]


def percentile_rank(df: pd.DataFrame) -> pd.DataFrame:
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"].rank(pct=True) * 100
    return out[["date", "value"]]


# ------------------------------------------------------------------ 结构
def share(df: pd.DataFrame, scale: float = 100.0) -> pd.DataFrame:
    """占比：每个值 / 全部值之和（横截面，如各行业占 GDP）。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"] / d["value"].sum() * scale
    return out[["date", "value"]]


def structure_change(df: pd.DataFrame) -> pd.DataFrame:
    """结构变化：当期占比 - 上期占比（百分点）。"""
    d = _sorted(df)
    out = d.copy()
    out["value"] = d["value"] - d["value"].shift(1)
    return out[["date", "value"]]


# ------------------------------------------------------------------ 双序列
def growth_contribution(component: pd.DataFrame, total: pd.DataFrame) -> pd.DataFrame:
    """增长贡献（%）：(Δcomponent_t) / (total_{t-1}) × 100。"""
    c, t = _align(component, total)
    out = c.copy()
    out["value"] = c["value"].diff() / t["value"].shift(1) * 100
    return out[["date", "value"]]


def per_capita(value: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """人均指标：value / population。"""
    v, p = _align(value, population)
    out = v.copy()
    out["value"] = v["value"] / p["value"]
    return out[["date", "value"]]


def nominal_to_real(nominal: pd.DataFrame, deflator: pd.DataFrame) -> pd.DataFrame:
    """名义值转实际值：nominal / deflator × 100（deflator 为指数）。"""
    n, d = _align(nominal, deflator)
    out = n.copy()
    out["value"] = n["value"] / d["value"] * 100
    return out[["date", "value"]]


# ------------------------------------------------------------------ 相关分析
def correlation(a: pd.DataFrame, b: pd.DataFrame) -> float:
    """皮尔逊相关系数（标量）。"""
    aa, bb = _align(a, b)
    return float(aa["value"].corr(bb["value"]))


def lag_correlation(a: pd.DataFrame, b: pd.DataFrame, max_lag: int = 12) -> pd.DataFrame:
    """滞后相关分析：b 滞后 a 的相关系数序列。返回 lag、correlation 表。"""
    aa, bb = _align(a, b)
    av = aa["value"].values
    bv = bb["value"].values
    out = []
    for lag in range(0, max_lag + 1):
        x = pd.Series(av[lag:] if lag else av)
        y = pd.Series(bv[: len(bv) - lag] if lag else bv)
        if len(x) < 3:
            out.append({"lag": lag, "correlation": np.nan})
            continue
        out.append({"lag": lag, "correlation": float(x.corr(y))})
    return pd.DataFrame(out)
