"""数据质量检查。

问题分三级：error（必须处理）/ warning（可继续但需说明）/ info（建议人工检查）。
任何检查都只报告，绝不静默填充缺失值或删除异常值。
"""
from __future__ import annotations

import pandas as pd

from macrosope.config import LEVEL_ERROR, LEVEL_WARNING
from macrosope.models import QualityReport

# 频率对应的典型日期间隔（天）
_FREQ_DAYS = [
    ("daily", 1),
    ("weekly", 7),
    ("monthly", 30),
    ("quarterly", 91),
    ("annual", 365),
]


def _freq_name(median_days: float) -> str:
    best, best_diff = "irregular", float("inf")
    for name, days in _FREQ_DAYS:
        d = abs(median_days - days)
        if d < best_diff:
            best, best_diff = name, d
    # 容许误差
    tol = {"daily": 0.5, "weekly": 1.5, "monthly": 4, "quarterly": 8, "annual": 20}
    if best in tol and best_diff <= tol[best]:
        return best
    return "irregular"


def detect_frequency(dates: pd.Series) -> tuple[str, bool]:
    """根据日期列推断频率与是否规则。

    返回 (频率名, 是否规则)。日期需已解析为 datetime。
    """
    d = pd.to_datetime(pd.Series(dates), errors="coerce").dropna().sort_values()
    if len(d) < 2:
        return "irregular", False
    diffs = d.diff().dt.days.dropna()
    if diffs.empty:
        return "irregular", False
    median = float(diffs.median())
    freq = _freq_name(median)
    # 规则性：绝大多数间隔与中位数接近
    tol = {"daily": 1, "weekly": 3, "monthly": 5, "quarterly": 12, "annual": 30}.get(freq, 0)
    if tol == 0:
        return freq, False
    regular = (diffs <= median + tol).all() and (diffs >= max(median - tol, 0)).all()
    return freq, bool(regular)


def _dup_rows(df: pd.DataFrame, cols: list[str]) -> list[int]:
    return df[df.duplicated(subset=cols, keep=False)].index.tolist()


def run_frame_checks(
    df: pd.DataFrame,
    date_col: str | None = None,
    value_col: str | None = None,
) -> QualityReport:
    """对单个 DataFrame 做纯数据层检查。"""
    report = QualityReport()

    # 1. 空文件
    if df.empty:
        report.add(LEVEL_ERROR, "empty_file", "文件为空，无任何数据")
        return report

    # 2. 空列（按位置访问，兼容重复列名）
    for i in range(df.shape[1]):
        if df.iloc[:, i].isna().all():
            report.add(
                LEVEL_ERROR, "empty_column",
                f"列「{df.columns[i]}」整列为空", column=str(df.columns[i]),
            )

    # 3. 重复列名
    dup_cols = df.columns[df.columns.duplicated()].unique().tolist()
    if dup_cols:
        report.add(
            LEVEL_ERROR,
            "duplicate_columns",
            f"存在重复列名：{dup_cols}，需先重命名",
            detail=str(dup_cols),
        )

    # 4. 重复记录
    all_cols = [str(c) for c in df.columns]
    dup_idx = _dup_rows(df, all_cols)
    if dup_idx:
        report.add(
            LEVEL_WARNING,
            "duplicate_records",
            f"存在 {len(dup_idx)} 行完全重复的记录",
            rows=dup_idx[:50],
        )

    # 5-8. 日期相关（需要日期列）
    if date_col is not None and date_col in df.columns:
        raw_dates = df[date_col]
        parsed = pd.to_datetime(raw_dates, errors="coerce")

        # 日期无法解析
        bad = raw_dates.notna() & parsed.isna()
        if bad.any():
            report.add(
                LEVEL_ERROR,
                "unparseable_dates",
                f"有 {int(bad.sum())} 个日期无法解析",
                column=date_col,
                rows=bad[bad].index.tolist()[:50],
            )

        # 重复日期
        if parsed.notna().any():
            dup_dates = parsed[parsed.notna()].duplicated(keep=False)
            dup_rows = dup_dates[dup_dates].index.tolist()
            if dup_rows:
                report.add(
                    LEVEL_ERROR,
                    "duplicate_dates",
                    f"存在 {len(dup_rows)} 行重复日期",
                    column=date_col,
                    rows=dup_rows[:50],
                )

            # 日期顺序错误
            if not parsed.dropna().is_monotonic_increasing:
                report.add(
                    LEVEL_WARNING,
                    "date_out_of_order",
                    "日期未按升序排列",
                    column=date_col,
                )

    # 9. 缺失值（按位置访问，兼容重复列名）
    missing_cols = []
    for i in range(df.shape[1]):
        n = int(df.iloc[:, i].isna().sum())
        if n > 0:
            missing_cols.append(f"「{df.columns[i]}」{n} 个")
    if missing_cols:
        report.add(
            LEVEL_WARNING,
            "missing_values",
            f"存在缺失值：{', '.join(missing_cols)}",
            detail="缺失值不会被静默填充，需在清洗步骤中选择处理方式",
        )

    # 10. 非数字值（需要数值列）
    if value_col is not None and value_col in df.columns:
        s = df[value_col]
        numeric = pd.to_numeric(s, errors="coerce")
        bad_num = s.notna() & numeric.isna()
        if bad_num.any():
            report.add(
                LEVEL_ERROR,
                "non_numeric_values",
                f"数值列「{value_col}」有 {int(bad_num.sum())} 个非数字值",
                column=value_col,
                rows=bad_num[bad_num].index.tolist()[:50],
            )

        # 11. 异常值（IQR）
        clean = numeric.dropna()
        if len(clean) >= 4:
            q1, q3 = clean.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                outliers = clean[(clean < lo) | (clean > hi)]
                if not outliers.empty:
                    report.add(
                        LEVEL_WARNING,
                        "outliers",
                        f"数值列「{value_col}」有 {len(outliers)} 个可能的异常值（IQR 法）",
                        column=value_col,
                        rows=outliers.index.tolist()[:50],
                        detail=f"区间 [{lo:.4g}, {hi:.4g}] 之外的值被视为异常",
                    )

    return report


def run_metadata_checks(series_metas: list[dict]) -> QualityReport:
    """对多序列做口径一致性检查（用于合并/制图前）。

    series_metas 每个元素需含 unit / currency / frequency / nominal_or_real /
    period_or_cumulative / seasonally_adjusted / name 等字段。
    """
    report = QualityReport()
    if len(series_metas) < 2:
        return report

    def _mixed(field: str, code: str, label: str) -> None:
        values = sorted({str(m.get(field, "") or "") for m in series_metas})
        values = [v for v in values if v and v != "unknown" and v != ""]
        if len(values) > 1:
            report.add(
                LEVEL_WARNING,
                code,
                f"{label}混杂：{', '.join(values)}",
                detail="合并或制图前请确认口径是否可比",
            )

    _mixed("unit", "mixed_units", "单位")
    _mixed("currency", "mixed_currencies", "币种")
    _mixed("frequency", "mixed_frequency", "频率")
    _mixed("nominal_or_real", "mixed_nominal_real", "名义值/实际值")
    _mixed("period_or_cumulative", "mixed_period_cumulative", "当期值/累计值")
    _mixed("seasonally_adjusted", "mixed_sa_nsa", "季调/未季调")

    # 百分数与小数据混杂：单位含 % 的序列与其他序列并存
    has_pct = any("%" in str(m.get("unit", "")) for m in series_metas)
    has_abs = any("%" not in str(m.get("unit", "")) for m in series_metas)
    if has_pct and has_abs:
        report.add(
            LEVEL_WARNING,
            "mixed_percent_decimal",
            "百分数（%）与绝对值序列并存，直接比较或叠加可能失真",
        )
    return report


def detect_percent_scale(values: pd.Series) -> bool:
    """启发式判断一列数值是否按百分数记录（如 5.0 表示 5%，而非 0.05）。"""
    s = pd.to_numeric(values, errors="coerce").dropna()
    if s.empty:
        return False
    return bool(((s.abs() > 1).mean() > 0.5) and (s.abs().max() > 10))
