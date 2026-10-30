"""序列级清洗变换。

所有清洗操作输入输出均为单序列 DataFrame（列：date、value）。
"""
from __future__ import annotations

import pandas as pd

_FILL_METHODS = ("keep", "drop", "ffill", "interp")


def sort_by_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """按日期去重，保留第一个。"""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")
    out = out.drop_duplicates(subset=["date"], keep="first").reset_index(drop=True)
    return out


def unit_convert(df: pd.DataFrame, factor: float) -> pd.DataFrame:
    """单位转换：value × factor。"""
    out = df.copy()
    out["value"] = out["value"].astype(float) * factor
    return out


def fill_missing(df: pd.DataFrame, method: str = "keep") -> pd.DataFrame:
    """缺失值处理。

    keep   —— 保持缺失（默认，不改动）
    drop   —— 删除含缺失的行
    ffill  —— 前向填充（可能造成数据失真，需用户主动选择）
    interp —— 线性插值（可能造成数据失真，需用户主动选择）
    """
    if method not in _FILL_METHODS:
        raise ValueError(f"未知缺失值处理方法：{method}")
    out = df.copy()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    if method == "keep":
        return out
    if method == "drop":
        return out.dropna(subset=["value"]).reset_index(drop=True)
    if method == "ffill":
        out["value"] = out["value"].ffill()
        return out
    if method == "interp":
        out["value"] = out["value"].interpolate(method="linear")
        return out
    return out


def manual_edit(df: pd.DataFrame, edits: list[dict]) -> pd.DataFrame:
    """手动修正单个值。edits 形如 [{"date": "2024-01", "value": 123.0}]。"""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for e in edits:
        d = pd.to_datetime(e["date"])
        out.loc[out["date"] == d, "value"] = float(e["value"])
    return out


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """标记异常值（IQR 法），返回含 is_outlier 列的 DataFrame，不删除数据。"""
    out = df.copy()
    v = pd.to_numeric(out["value"], errors="coerce")
    if len(v.dropna()) < 4:
        out["is_outlier"] = False
        return out
    q1, q3 = v.quantile([0.25, 0.75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    out["is_outlier"] = (v < lo) | (v > hi)
    return out
