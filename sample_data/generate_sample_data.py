"""生成完全虚构的示例经济数据（用于演示与测试）。

所有数据均为合成数据，不代表真实经济情况。
生成的文件直接写入本目录（sample_data/），覆盖已有同名文件。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
rng = np.random.default_rng(42)

MONTHS = pd.date_range("2020-01-01", "2024-12-01", freq="MS")
QUARTERS = pd.date_range("2020-01-01", "2024-10-01", freq="QS")


def _series(base: float, drift: float, noise: float, n: int) -> np.ndarray:
    t = np.arange(n, dtype=float)
    return base + drift * t + rng.normal(0, noise, n)


def gen_wide_csv() -> None:
    """宽表：日期 + 多个指标列（CPI同比、PPI同比、M2同比），UTF-8。"""
    n = len(MONTHS)
    df = pd.DataFrame({
        "日期": MONTHS,
        "CPI同比": _series(2.0, 0.01, 0.4, n).round(2),
        "PPI同比": _series(-1.0, -0.02, 0.8, n).round(2),
        "M2同比": _series(10.0, -0.03, 0.5, n).round(2),
    })
    df.to_csv(HERE / "cpi_ppi_m2_wide.csv", index=False, encoding="utf-8-sig")
    print("已生成 cpi_ppi_m2_wide.csv")


def gen_long_csv() -> None:
    """长表：日期 + 指标 + 数值 + 单位（GDP、固定资产投资，季度）。"""
    n = len(QUARTERS)
    gdp = _series(25.0, 1.5, 0.5, n)
    fai = _series(40.0, 1.2, 1.0, n)
    df = pd.DataFrame({
        "日期": list(QUARTERS) + list(QUARTERS),
        "指标": ["GDP"] * n + ["固定资产投资"] * n,
        "数值": list(gdp) + list(fai),
        "单位": ["万亿元"] * n + ["万亿元"] * n,
    })
    df.to_csv(HERE / "gdp_investment_long.csv", index=False, encoding="utf-8-sig")
    print("已生成 gdp_investment_long.csv")


def gen_gbk_csv() -> None:
    """GBK 编码、分号分隔、带千分位与百分号的 CSV（用于测试编码/分隔符）。"""
    n = 12
    df = pd.DataFrame({
        "月份": pd.date_range("2024-01-01", periods=n, freq="MS"),
        "社会融资规模存量": (_series(300.0, 2.0, 0.5, n) * 1).round(1),
        "人民币贷款": (_series(200.0, 1.5, 0.3, n)).round(1),
        "同比增长": _series(8.0, -0.1, 0.3, n).round(2),
    })
    # 千位分隔符
    df["社会融资规模存量"] = df["社会融资规模存量"].map(lambda v: f"{v:,.1f}")
    # 百分号
    df["同比增长"] = df["同比增长"].map(lambda v: f"{v}%")
    df.to_csv(HERE / "social_finance_gbk.csv", index=False, encoding="gbk", sep=";")
    print("已生成 social_finance_gbk.csv（GBK + 分号 + 千分位 + 百分号）")


def gen_excel() -> None:
    """多工作表 Excel：CPI、M2、贸易 三张表。"""
    cpi = pd.DataFrame({
        "月份": MONTHS,
        "CPI同比(%)": _series(2.0, 0.01, 0.4, len(MONTHS)).round(2),
        "食品价格": _series(3.0, -0.01, 1.0, len(MONTHS)).round(2),
    })
    m2 = pd.DataFrame({
        "月份": MONTHS,
        "M2余额(亿元)": (_series(2_000_000, 20_000, 2_000, len(MONTHS))).round(0),
        "M1余额(亿元)": (_series(600_000, 5_000, 1_000, len(MONTHS))).round(0),
    })
    trade = pd.DataFrame({
        "月份": MONTHS,
        "出口(亿美元)": (_series(2_000, 30, 100, len(MONTHS))).round(0),
        "进口(亿美元)": (_series(1_800, 25, 90, len(MONTHS))).round(0),
    })
    with pd.ExcelWriter(HERE / "macro_monthly.xlsx", engine="openpyxl") as w:
        cpi.to_excel(w, sheet_name="CPI", index=False)
        m2.to_excel(w, sheet_name="货币", index=False)
        trade.to_excel(w, sheet_name="贸易", index=False)
    print("已生成 macro_monthly.xlsx（多工作表）")


def gen_json() -> None:
    """JSON records：人口与就业（年度）。"""
    years = list(range(2015, 2025))
    df = pd.DataFrame({
        "年份": years,
        "总人口(万人)": _series(140_000, 100, 50, len(years)).round(0),
        "就业人员(万人)": _series(75_000, -200, 60, len(years)).round(0),
    })
    df.to_json(HERE / "population.json", orient="records", force_ascii=False)
    print("已生成 population.json")


def gen_parquet() -> None:
    """Parquet：进出口与贸易差额（月度）。"""
    n = len(MONTHS)
    export = _series(2_000, 30, 100, n).round(0)
    import_ = _series(1_800, 25, 90, n).round(0)
    df = pd.DataFrame({
        "日期": MONTHS,
        "出口": export,
        "进口": import_,
        "贸易差额": export - import_,
    })
    df.to_parquet(HERE / "trade.parquet", index=False)
    print("已生成 trade.parquet")


if __name__ == "__main__":
    gen_wide_csv()
    gen_long_csv()
    gen_gbk_csv()
    gen_excel()
    gen_json()
    gen_parquet()
    print("示例数据生成完毕。")
