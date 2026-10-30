"""导出器：CSV / XLSX / Parquet / PNG / SVG / HTML / JSON。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from macrosope.export.safety import safe_join, sanitize_dataframe


def _resolve(base_dir: str | Path, filename: str) -> Path:
    return safe_join(base_dir, filename)


def export_csv(df: pd.DataFrame, base_dir: str | Path, filename: str) -> str:
    """导出清洗后的 CSV（UTF-8-SIG，Excel 兼容），并做公式注入防护。"""
    path = _resolve(base_dir, filename)
    safe = sanitize_dataframe(df)
    safe.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def export_xlsx(df: pd.DataFrame, base_dir: str | Path, filename: str) -> str:
    path = _resolve(base_dir, filename)
    safe = sanitize_dataframe(df)
    safe.to_excel(path, index=False, engine="openpyxl")
    return str(path)


def export_parquet(df: pd.DataFrame, base_dir: str | Path, filename: str) -> str:
    path = _resolve(base_dir, filename)
    df.to_parquet(path, index=False)
    return str(path)


def export_figure(fig, base_dir: str | Path, filename: str, fmt: str) -> str:
    """导出图表。HTML 自包含；PNG/SVG 需要 Kaleido 和本机 Chrome。"""
    path = _resolve(base_dir, filename)
    if fmt == "html":
        fig.write_html(str(path), include_plotlyjs=True)
    elif fmt in ("png", "svg"):
        try:
            fig.write_image(str(path), format=fmt, scale=2)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"导出 {fmt.upper()} 失败（需 Kaleido 和 Chrome；可改用 HTML）：{exc}"
            ) from exc
    else:
        raise ValueError(f"不支持的图表导出格式：{fmt}")
    return str(path)


def to_json(obj, base_dir: str | Path, filename: str) -> str:
    path = _resolve(base_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    return str(path)
