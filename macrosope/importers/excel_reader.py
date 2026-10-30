"""Excel 读取器。

支持选择工作表、设置表头行、跳过顶部说明、检查合并单元格与重复列名。
第一版拒绝 XLSM（含宏）文件，绝不执行宏。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from macrosope.importers.base import PreviewResult


def _reject_macro(path: Path) -> None:
    if path.suffix.lower() == ".xlsm":
        raise ValueError("已拒绝 XLSM 文件：含宏的 Excel 第一版不支持（安全起见不执行宏）。")


def list_sheets(path: str | Path) -> list[str]:
    """列出 Excel 文件的所有工作表名。"""
    path = Path(path)
    _reject_macro(path)
    xl = pd.ExcelFile(path, engine="openpyxl")
    try:
        return list(xl.sheet_names)
    finally:
        xl.close()


def detect_merged_cells(path: str | Path, sheet_name: str) -> list[str]:
    """返回指定工作表内的合并单元格区域描述（如 "A1:B2"）。"""
    from openpyxl import load_workbook

    path = Path(path)
    _reject_macro(path)
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb[sheet_name]
        return [str(rng) for rng in ws.merged_cells.ranges]
    finally:
        wb.close()


def read_excel(
    path: str | Path,
    sheet_name: str | int | None = None,
    header_row: int | None = 0,
    skiprows: int = 0,
    **_: object,
) -> PreviewResult:
    """读取 Excel 工作表为字符串型 DataFrame。"""
    path = Path(path)
    _reject_macro(path)

    if sheet_name is None:
        sheet_name = 0  # 默认第一张表
    header = None if header_row is None else header_row
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=header,
        skiprows=skiprows,
        dtype=object,
        engine="openpyxl",
    )

    issues: list[dict] = []
    if df.empty:
        issues.append({"level": "error", "code": "empty_file", "message": "文件为空"})

    # 重复列名检查
    dup_cols = df.columns[df.columns.duplicated()].unique().tolist()
    if dup_cols:
        issues.append(
            {
                "level": "warning",
                "code": "duplicate_columns",
                "message": f"存在重复列名：{dup_cols}",
            }
        )

    # 合并单元格检查（仅在给出工作表名时）
    merged: list[str] = []
    try:
        if isinstance(sheet_name, str):
            merged = detect_merged_cells(path, sheet_name)
    except Exception:  # noqa: BLE001 —— 合并单元格检测失败不应阻断导入
        merged = []
    if merged:
        issues.append(
            {
                "level": "info",
                "code": "merged_cells",
                "message": f"检测到 {len(merged)} 个合并单元格，请确认表头行设置正确",
                "detail": "; ".join(merged[:20]),
            }
        )

    if header_row is None:
        df.columns = [f"列{i + 1}" for i in range(len(df.columns))]

    settings = {"sheet_name": str(sheet_name), "header_row": header_row, "skiprows": skiprows}
    sheet_names = list_sheets(path)
    return PreviewResult(df=df, settings=settings, issues=issues, sheet_names=sheet_names)
