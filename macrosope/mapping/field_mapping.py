"""字段角色建议与宽/长表转换。

自动识别（suggest_roles）仅作为建议，绝不未经确认直接修改数据。
宽表/长表转换只在用户确认映射后由 to_long / to_wide 执行。
"""
from __future__ import annotations

import pandas as pd

# 列名关键词 -> 角色（中英文，按优先级）
_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "date": ("date", "日期", "时间", "time", "period", "月", "季度", "quarter", "year", "年", "日", "day"),
    "indicator": ("指标", "indicator", "名称", "name", "series", "variable", "科目", "项目", "item"),
    "value": ("数值", "value", "amount", "数据", "金额", "余额", "值"),
    "entity": ("地区", "国家", "省份", "region", "country", "province", "entity", "area", "city", "城市", "主体"),
    "unit": ("单位", "unit"),
    "frequency": ("频率", "频度", "freq"),
    "source": ("来源", "source", "机构", "数据源"),
    "note": ("备注", "说明", "note", "remark", "comment", "注释"),
}

# 每类角色最多允许的列数（date/indicator/value 通常为 1，value 在宽表中可为多列）
_ROLE_LIMIT = {"date": 1, "indicator": 1, "entity": 1, "unit": 1, "frequency": 1, "source": 1, "note": 1}


def _guess_role(name: str) -> str | None:
    n = str(name).lower().strip()
    for role, kws in _ROLE_KEYWORDS.items():
        for kw in kws:
            if kw in n:
                return role
    return None


def _looks_like_date(col: pd.Series) -> bool:
    """判断一列是否像日期（抽样尝试解析）。"""
    if pd.api.types.is_datetime64_any_dtype(col):
        return True
    sample = col.dropna().astype(str).head(20)
    if sample.empty:
        return False
    try:
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        return parsed.notna().mean() > 0.8
    except Exception:  # noqa: BLE001
        return False


def suggest_roles(df: pd.DataFrame) -> dict[str, str]:
    """为每一列建议角色。纯建议，需用户确认。"""
    roles: dict[str, str] = {}
    for col in df.columns:
        role = _guess_role(str(col))
        if role is None:
            if _looks_like_date(df[col]):
                role = "date"
            elif pd.api.types.is_numeric_dtype(df[col]):
                role = "value"
            else:
                role = "ignore"
        roles[str(col)] = role
    return roles


def detect_layout(roles: dict[str, str]) -> str:
    """根据角色映射判断是宽表还是长表。"""
    return "long" if "indicator" in roles.values() else "wide"


def _unique_role_col(roles: dict[str, str], role: str) -> str | None:
    cols = [c for c, r in roles.items() if r == role]
    return cols[0] if len(cols) == 1 else None


def to_long(df: pd.DataFrame, roles: dict[str, str]) -> pd.DataFrame:
    """宽表 -> 长表。

    宽表要求：一个 date 列 + 一个或多个 value 列（每列是一个指标）。
    可选 entity/unit/frequency/source/note 列（各至多一列）。
    输出列顺序：date, entity, indicator, value, unit, frequency, source, note。
    """
    date_col = _unique_role_col(roles, "date")
    value_cols = [c for c, r in roles.items() if r == "value"]
    if date_col is None:
        raise ValueError("宽表转长表需要一个唯一的日期列")
    if not value_cols:
        raise ValueError("宽表转长表需要至少一个数值列")

    id_cols = [date_col]
    extra: dict[str, str | None] = {}
    for role in ("entity", "unit", "frequency", "source", "note"):
        col = _unique_role_col(roles, role)
        extra[role] = col
        if col is not None:
            id_cols.append(col)

    # pandas 禁止 value_name 与输入列重名；英文数据常直接使用 value 列。
    value_name = "__macrosope_value__"
    while value_name in df.columns:
        value_name += "_"
    melted = df.melt(
        id_vars=id_cols,
        value_vars=value_cols,
        var_name="indicator",
        value_name=value_name,
    ).rename(columns={value_name: "value"})

    out_cols = [date_col]
    rename = {date_col: "date"}
    if extra["entity"] is not None:
        out_cols.append(extra["entity"])
        rename[extra["entity"]] = "entity"
    out_cols += ["indicator", "value"]
    if extra["unit"] is not None:
        out_cols.append(extra["unit"])
        rename[extra["unit"]] = "unit"
    if extra["frequency"] is not None:
        out_cols.append(extra["frequency"])
        rename[extra["frequency"]] = "frequency"
    if extra["source"] is not None:
        out_cols.append(extra["source"])
        rename[extra["source"]] = "source"
    if extra["note"] is not None:
        out_cols.append(extra["note"])
        rename[extra["note"]] = "note"

    result = melted[out_cols].rename(columns=rename)
    return result


def to_wide(df: pd.DataFrame, roles: dict[str, str]) -> pd.DataFrame:
    """长表 -> 宽表。

    长表要求：date + indicator + value 列；可选 entity 列。
    输出：以 date（和 entity）为行索引，每个 indicator 一列。
    """
    date_col = _unique_role_col(roles, "date")
    indicator_col = _unique_role_col(roles, "indicator")
    value_col = _unique_role_col(roles, "value")
    entity_col = _unique_role_col(roles, "entity")
    if date_col is None or indicator_col is None or value_col is None:
        raise ValueError("长表转宽表需要唯一的日期列、指标名称列和数值列")

    index = [date_col] + ([entity_col] if entity_col else [])
    pivoted = df.pivot_table(
        index=index,
        columns=indicator_col,
        values=value_col,
        aggfunc="first",
    )
    pivoted = pivoted.reset_index()
    pivoted.columns.name = None
    return pivoted
