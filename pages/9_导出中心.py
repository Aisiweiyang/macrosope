"""导出中心页：数据、图表、配置、管道、项目备份。"""
from __future__ import annotations

import streamlit as st
from macrosope.charts import build_figure, prepare_series_data
from macrosope.config import EXPORT_DIR
from macrosope.export import (
    export_csv,
    export_figure,
    export_parquet,
    export_xlsx,
    sanitize_filename,
    to_json,
)
from macrosope.ui import get_repo, series_options

repo = get_repo()

st.title("📤 导出中心")
st.caption("导出目录：`data/exports/`。已内置 CSV 公式注入与文件名路径穿越防护。")

tab1, tab2, tab3 = st.tabs(["数据", "图表", "配置与备份"])

with tab1:
    opts = series_options(repo)
    if opts:
        selected = st.multiselect("选择序列", list(opts.keys()))
        if selected:
            series_ids = [opts[lab] for lab in selected]
            if len(series_ids) == 1:
                df = repo.get_observations(series_ids[0])
            else:
                df = prepare_series_data(repo, series_ids)
            st.dataframe(df.head(50), use_container_width=True)
            fname = sanitize_filename("_".join(selected)[:40]) + "_export"
            if st.button("导出 CSV"):
                st.success(export_csv(df, EXPORT_DIR, fname + ".csv"))
            if st.button("导出 XLSX"):
                st.success(export_xlsx(df, EXPORT_DIR, fname + ".xlsx"))
            if st.button("导出 Parquet"):
                st.success(export_parquet(df, EXPORT_DIR, fname + ".parquet"))
    else:
        st.info("暂无序列。")

with tab2:
    charts = repo.list_charts()
    if charts:
        cnames = {f"#{c.chart_id} {c.name}": c.chart_id for c in charts}
        sel = st.selectbox("选择图表", list(cnames.keys()))
        fmt = st.selectbox("导出格式", ["png", "svg", "html"])
        if st.button("导出图表"):
            spec = next(c for c in charts if c.chart_id == cnames[sel])
            data = prepare_series_data(repo, spec.series_ids)
            fig = build_figure(spec, data)
            base = sanitize_filename(spec.name)
            try:
                path = export_figure(fig, EXPORT_DIR, f"{base}.{fmt}", fmt)
                st.success(path)
            except RuntimeError as exc:
                st.error(str(exc))
    else:
        st.info("暂无保存的图表。")

with tab3:
    if st.button("导出变换管道 JSON"):
        steps = [s.model_dump() for s in repo.list_steps()]
        st.success(to_json(steps, EXPORT_DIR, "pipeline.json"))
    if st.button("导出全部图表配置 JSON"):
        cfgs = [c.model_dump() for c in repo.list_charts()]
        st.success(to_json(cfgs, EXPORT_DIR, "charts_config.json"))
    if st.button("导出指标元数据 JSON"):
        inds = [i.model_dump() for i in repo.list_indicators()]
        st.success(to_json(inds, EXPORT_DIR, "indicators.json"))
