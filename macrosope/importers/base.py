"""导入公共设施：编码/分隔符检测、数值清洗、统一读取入口。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from macrosope.config import SUPPORTED_FORMATS

# 常见中文编码，按优先级排列
_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin-1")

_DELIMITERS = (",", "\t", ";", "|")


@dataclass
class PreviewResult:
    """读取结果：数据帧 + 实际使用的设置 + 读取期发现的问题。"""

    df: pd.DataFrame
    settings: dict = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    sheet_names: list[str] = field(default_factory=list)


def detect_encoding(raw: bytes) -> str:
    """按优先级探测编码，返回第一个能无错解码的编码名。"""
    for enc in _ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def detect_delimiter(text: str) -> str:
    """用 csv.Sniffer 探测分隔符，失败则回退到计数法。"""
    import csv

    sample = "\n".join(text.splitlines()[:20])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_DELIMITERS))
        return dialect.delimiter
    except csv.Error:
        pass
    # 计数回退：选在首行出现次数最多且各行列数一致的候选
    lines = [ln for ln in sample.splitlines() if ln.strip()]
    if not lines:
        return ","
    best, best_score = ",", -1
    for d in _DELIMITERS:
        counts = [ln.count(d) for ln in lines]
        if len(set(counts)) == 1 and counts[0] > 0 and counts[0] > best_score:
            best, best_score = d, counts[0]
    return best


def clean_number(value, thousands_sep: str | None = ",", percent: bool = True) -> str:
    """把单个字符串数值清洗为可解析形式（去掉千分位、百分号、括号负号）。"""
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s == "":
        return s
    # 括号表示负数：(1,234) -> -1234
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    if percent and s.endswith("%"):
        s = s[:-1].strip()
        # 百分号：保留为字符串标记，之后统一除以 100
        s = f"__PERCENT__{s}"
    if thousands_sep and thousands_sep in s:
        s = s.replace(thousands_sep, "")
    # 中文千分位/单位：全角逗号
    s = s.replace("，", "").replace(" ", "").replace(" ", "")
    if negative:
        s = f"-{s}" if not s.startswith("-") else s[1:]
    return s


def _to_numeric(s: pd.Series, thousands_sep: str | None, percent: bool):
    """把一列字符串尝试转为数值列；仅对带 % 的单元格除以 100，不污染同列绝对值。"""
    cleaned = s.map(lambda v: clean_number(v, thousands_sep, percent))
    is_pct = cleaned.astype(str).str.contains("__PERCENT__", na=False)
    cleaned = cleaned.astype(str).str.replace("__PERCENT__", "", regex=False)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    # 若绝大多数非空值能转成数字，则视为数值列
    non_null = cleaned.notna() & (cleaned.astype(str).str.strip() != "")
    ratio = numeric.notna().sum() / non_null.sum() if non_null.sum() > 0 else 0.0
    if ratio >= 0.9:
        if is_pct.any():
            # 只对带百分号的单元格除以 100
            numeric = numeric.where(~is_pct, numeric / 100.0)
        return numeric, "numeric"
    return s, "text"


def normalize_dataframe(
    df: pd.DataFrame,
    thousands_sep: str | None = ",",
    percent: bool = True,
) -> tuple[pd.DataFrame, list[dict]]:
    """把字符串型 DataFrame 规范化：数值列转 float、百分号列除以 100。

    返回 (规范化后的 df, 每列转换情况列表)。绝不静默删除或填充值。
    """
    out = df.copy()
    conversions: list[dict] = []
    for col in out.columns:
        is_text = pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(
            out[col]
        )
        if is_text:
            newcol, kind = _to_numeric(out[col], thousands_sep, percent)
            if kind == "numeric":
                out[col] = newcol
                conversions.append({"column": str(col), "converted_to": "float"})
            else:
                conversions.append({"column": str(col), "converted_to": "kept_text"})
        else:
            conversions.append({"column": str(col), "converted_to": "kept"})
    return out, conversions


def read_file(path: str | Path, **kwargs) -> PreviewResult:
    """按扩展名分发到对应读取器。"""
    path = Path(path)
    ext = path.suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的格式：{ext}（支持 {SUPPORTED_FORMATS}）")
    if ext == "csv":
        from macrosope.importers.csv_reader import read_csv

        return read_csv(path, **kwargs)
    if ext in ("xlsx", "xls"):
        from macrosope.importers.excel_reader import read_excel

        return read_excel(path, **kwargs)
    if ext == "json":
        from macrosope.importers.json_reader import read_json

        return read_json(path, **kwargs)
    if ext == "parquet":
        from macrosope.importers.parquet_reader import read_parquet

        return read_parquet(path, **kwargs)
    raise ValueError(f"不支持的格式：{ext}")
