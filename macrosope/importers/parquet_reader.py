"""Parquet 读取器。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from macrosope.importers.base import PreviewResult


def read_parquet(path: str | Path, **_: object) -> PreviewResult:
    path = Path(path)
    df = pd.read_parquet(path)

    issues: list[dict] = []
    if df.empty:
        issues.append({"level": "error", "code": "empty_file", "message": "文件为空"})
    return PreviewResult(df=df, settings={}, issues=issues)
