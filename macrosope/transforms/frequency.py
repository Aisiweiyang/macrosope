"""频率转换。

第一版只做降频（低频化），禁止把低频数据插值成伪造的高频数据。
聚合方法：求和/平均/期初/期末/最大/最小。
"""
from __future__ import annotations

import pandas as pd

from macrosope.config import FREQ_ALIAS, FREQUENCIES

# 频率排序：0 最高频，4 最低频
_FREQ_ORDER = {"daily": 0, "weekly": 1, "monthly": 2, "quarterly": 3, "annual": 4}

_AGG = {
    "sum": "sum",
    "mean": "mean",
    "first": "first",
    "last": "last",
    "max": "max",
    "min": "min",
}


def validate_freq_conversion(from_freq: str, to_freq: str) -> None:
    """校验频率转换方向；升频（如月度→日度）直接拒绝。"""
    if from_freq not in _FREQ_ORDER or to_freq not in _FREQ_ORDER:
        return  # 未知频率不做强制校验
    if _FREQ_ORDER[to_freq] < _FREQ_ORDER[from_freq]:
        raise ValueError(
            f"禁止把低频数据升频为高频：{from_freq} → {to_freq}。"
            "低频数据插值成高频属于伪造数据。"
        )


def suggest_agg_method(stock_or_flow: str = "unknown", unit: str = "") -> str:
    """根据口径建议聚合方法：流量→求和，存量→期末，利率/价格→平均或期末。"""
    if stock_or_flow == "flow":
        return "sum"
    if stock_or_flow == "stock":
        return "last"
    ul = unit.lower()
    if any(k in ul for k in ("%", "率", "利率", "收益率", "价格", "指数")):
        return "mean"
    return "mean"


def resample(df: pd.DataFrame, to_freq: str, method: str = "sum") -> pd.DataFrame:
    """把序列降频到 to_freq，用 method 聚合。"""
    if to_freq not in FREQUENCIES:
        raise ValueError(f"未知目标频率：{to_freq}")
    if method not in _AGG:
        raise ValueError(f"未知聚合方法：{method}")
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date"]).sort_values("date").set_index("date")
    res = d["value"].resample(FREQ_ALIAS[to_freq]).agg(_AGG[method]).reset_index()
    return res[["date", "value"]]
