"""导出安全防护：CSV 公式注入与文件名路径穿越。"""
from __future__ import annotations

import re
from pathlib import Path

# 文件系统非法字符与控制字符
_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """清洗文件名：去除路径分隔符与非法字符，防止路径穿越。"""
    name = _FORBIDDEN.sub("_", name)
    name = name.strip(". ")
    return name or "export"


def safe_join(base_dir: str | Path, filename: str) -> Path:
    """把 filename 安全拼接到 base_dir 下，确保结果仍在 base_dir 内。"""
    base = Path(base_dir).resolve()
    candidate = (base / filename).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"非法文件名（路径穿越）：{filename}")
    return candidate


def sanitize_cell(value):
    """防 CSV 公式注入：以 = + - @ 或制表符/回车开头的字符串前加单引号。"""
    if isinstance(value, str) and value and value[0] in "=+-@\t\r":
        return "'" + value
    return value


def sanitize_dataframe(df):
    """对 DataFrame 所有字符串单元格做公式注入清洗。"""
    import pandas as pd


    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(
            out[col]
        ):
            out[col] = out[col].map(sanitize_cell)
    return out
