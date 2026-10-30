"""仪表盘页：展示已保存的图表。"""
from __future__ import annotations

import streamlit as st
from macrosope.charts import build_figure, prepare_series_data
from macrosope.ui import get_repo

repo = get_repo()

st.title("📊 仪表盘")

charts = repo.list_charts()
if not charts:
    st.info("还没有保存的图表。请到「图表生成器」页创建并保存。")
    st.stop()

for spec in charts:
    data = prepare_series_data(repo, spec.series_ids)
    with st.container():
        st.markdown(f"#### {spec.name}　`{spec.chart_type}`")
        fig = build_figure(spec, data)
        st.plotly_chart(fig, use_container_width=True)
