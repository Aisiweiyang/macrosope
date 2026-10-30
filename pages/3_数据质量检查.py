"""数据质量检查页：对序列做数据层与口径层检查。"""
from __future__ import annotations

import streamlit as st
from macrosope.quality import run_frame_checks, run_metadata_checks
from macrosope.ui import get_repo, render_quality_report, series_options

repo = get_repo()

st.title("🔍 数据质量检查")
st.caption("问题分三级：错误（必须处理）/ 警告（可继续但需说明）/ 提示（建议人工检查）。绝不静默处理。")

opts = series_options(repo)
if not opts:
    st.info("还没有序列，请先导入数据。")
    st.stop()

selected_labels = st.multiselect("选择要检查的序列", list(opts.keys()))
if not selected_labels:
    st.stop()

series_ids = [opts[lab] for lab in selected_labels]

st.subheader("数据层检查（逐序列）")
for sid in series_ids:
    meta = repo.get_series(sid)
    label = meta.get("indicator_name") or f"序列{sid}"
    df = repo.get_observations(sid)
    rep = run_frame_checks(df, date_col="date", value_col="value")
    if rep.issues:
        st.markdown(f"**{label}**")
        render_quality_report(rep)

st.subheader("口径一致性检查（跨序列）")
metas = []
for sid in series_ids:
    m = repo.get_series(sid)
    if m is None:
        continue
    ind = repo.get_indicator(m["indicator_id"])
    metas.append({**m, **(ind.model_dump() if ind else {})})
meta_rep = run_metadata_checks(metas)
render_quality_report(meta_rep)

if st.button("导出本次质量报告 JSON"):
    from macrosope.config import EXPORT_DIR
    from macrosope.export import to_json

    all_issues = []
    for sid in series_ids:
        df = repo.get_observations(sid)
        rep = run_frame_checks(df, date_col="date", value_col="value")
        all_issues.extend([i.model_dump() for i in rep.issues])
    all_issues.extend([i.model_dump() for i in meta_rep.issues])
    path = to_json(all_issues, EXPORT_DIR, "quality_report.json")
    st.success(f"已导出到 {path}")
