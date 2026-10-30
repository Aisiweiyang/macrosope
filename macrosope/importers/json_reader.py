"""JSON 读取器。

支持 records / 列表、表格（columns）等常见 JSON 结构。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from macrosope.importers.base import PreviewResult


def read_json(
    path: str | Path,
    orient: str | None = None,
    **_: object,
) -> PreviewResult:
    """读取 JSON 文件为 DataFrame。

    orient 为 pandas 的 orient 参数（records/columns/index/split/table）。
    未指定时尝试自动判断。
    """
    path = Path(path)
    df = pd.read_json(path, orient=orient, dtype=object)

    issues: list[dict] = []
    if df.empty:
        issues.append({"level": "error", "code": "empty_file", "message": "文件为空"})
    if orient is None:
        orient = "auto"
    settings = {"orient": orient}
    return PreviewResult(df=df, settings=settings, issues=issues)
