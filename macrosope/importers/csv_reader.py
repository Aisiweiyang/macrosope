"""CSV 读取器。

支持：UTF-8 及常见中文编码、分隔符识别、表头行指定、跳过顶部说明行。
百分号与千位分隔符的规范化由 normalize_dataframe 在确认阶段完成。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from macrosope.importers.base import (
    PreviewResult,
    detect_delimiter,
    detect_encoding,
)


def read_csv(
    path: str | Path,
    encoding: str | None = None,
    delimiter: str | None = None,
    header_row: int | None = 0,
    skiprows: int = 0,
    date_format: str | None = None,
    **_: object,
) -> PreviewResult:
    """读取 CSV 文件为字符串型 DataFrame。

    header_row 为表头所在行（0-based，None 表示无表头）。
    skiprows 为表头前需要跳过的说明行数。
    """
    path = Path(path)
    raw = path.read_bytes()
    if encoding is None:
        encoding = detect_encoding(raw)

    if delimiter is None:
        try:
            text = raw.decode(encoding)
            delimiter = detect_delimiter(text)
        except (UnicodeDecodeError, LookupError):
            delimiter = ","

    header = None if header_row is None else header_row
    df = pd.read_csv(
        path,
        encoding=encoding,
        sep=delimiter,
        header=header,
        skiprows=skiprows,
        dtype=object,
        keep_default_na=True,
    )

    issues: list[dict] = []
    if df.empty:
        issues.append({"level": "error", "code": "empty_file", "message": "文件为空"})
    if header_row is None:
        df.columns = [f"列{i + 1}" for i in range(len(df.columns))]

    settings = {
        "encoding": encoding,
        "delimiter": delimiter,
        "header_row": header_row,
        "skiprows": skiprows,
        "date_format": date_format,
    }
    return PreviewResult(df=df, settings=settings, issues=issues)
