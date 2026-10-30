"""Streamlit 共享工具：缓存的 Repository/Pipeline 与通用渲染。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from macrosope.db import Repository
from macrosope.models import QualityReport
from macrosope.transforms import Pipeline


@st.cache_resource
def get_repo() -> Repository:
    return Repository()


@st.cache_resource
def get_pipeline() -> Pipeline:
    return Pipeline(get_repo())


def series_label(s: dict) -> str:
    name = s.get("indicator_name") or f"序列{s['series_id']}"
    parts = [str(name)]
    if s.get("entity"):
        parts.append(f"[{s['entity']}]")
    if s.get("frequency"):
        parts.append(f"({s['frequency']})")
    if s.get("unit"):
        parts.append(str(s["unit"]))
    return " ".join(parts)


def series_options(repo: Repository) -> dict[str, int]:
    return {series_label(s): s["series_id"] for s in repo.list_series()}


def render_quality_report(report: QualityReport) -> None:
    if not report.issues:
        st.success("未发现问题")
        return
    for level, label, icon in [
        ("error", "错误", "❌"),
        ("warning", "警告", "⚠️"),
        ("info", "提示", "ℹ️"),
    ]:
        items = report.by_level(level)
        if not items:
            continue
        with st.expander(f"{icon} {label}（{len(items)}）", expanded=(level == "error")):
            for it in items:
                loc = f"　列「{it.column}」" if it.column else ""
                if it.rows:
                    loc += f"　行 {[r + 1 for r in it.rows[:10]]}"
                st.write(f"- **{it.code}**：{it.message}{loc}")
                if it.detail:
                    st.caption(it.detail)


def fmt_df_preview(df: pd.DataFrame, n: int = 100) -> pd.DataFrame:
    return df.head(n)


def long_series_df(repo: Repository, series_ids: list[int]) -> pd.DataFrame:
    from macrosope.charts import prepare_series_data

    return prepare_series_data(repo, series_ids)
