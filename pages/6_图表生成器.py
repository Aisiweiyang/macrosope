"""图表生成器页：选序列 → 选类型 → 可信度检查 → 生成 → 保存。"""
from __future__ import annotations

import streamlit as st
from macrosope.charts import build_figure, check_chart, prepare_series_data
from macrosope.models import ChartSpec
from macrosope.ui import get_repo, render_quality_report, series_options

repo = get_repo()

st.title("📈 图表生成器")

CHART_TYPES = {
    "line": "折线图",
    "bar": "柱状图",
    "area": "面积图",
    "scatter": "散点图",
    "heatmap": "相关性热力图",
    "histogram": "直方图",
    "box": "箱线图",
    "stacked_bar": "堆叠柱状图",
    "dual_axis": "双轴图（谨慎使用）",
}

opts = series_options(repo)
if not opts:
    st.info("还没有序列，请先导入数据。")
    st.stop()

selected = st.multiselect("选择序列", list(opts.keys()))
if not selected:
    st.stop()
series_ids = [opts[lab] for lab in selected]

chart_type = st.selectbox("图表类型", list(CHART_TYPES.keys()), format_func=lambda c: CHART_TYPES[c])

with st.expander("标注与选项", expanded=True):
    c1, c2 = st.columns(2)
    title = c1.text_input("标题", "")
    subtitle = c2.text_input("副标题", "")
    c3, c4 = st.columns(2)
    x_label = c3.text_input("横轴标签", "日期")
    y_label = c4.text_input("纵轴标签", "")
    c5, c6 = st.columns(2)
    unit = c5.text_input("单位", "")
    source = c6.text_input("数据来源", "")
    c7, c8 = st.columns(2)
    footnote = c7.text_input("图下注释", "")
    updated_at = c8.text_input("数据更新时间", "")
    c9, c10, c11 = st.columns(3)
    log_y = c9.checkbox("对数坐标")
    decimals = c10.number_input("小数位数", 0, 6, 2)
    show_legend = c11.checkbox("显示图例", value=True)
    width = st.slider("宽度", 400, 1600, 900, 50)
    height = st.slider("高度", 300, 1200, 500, 50)

spec = ChartSpec(
    name=title or f"{CHART_TYPES[chart_type]}",
    chart_type=chart_type,
    series_ids=series_ids,
    title=title,
    subtitle=subtitle,
    x_label=x_label,
    y_label=y_label,
    unit=unit,
    source=source,
    footnote=footnote,
    updated_at=updated_at,
    options={
        "log_y": log_y,
        "decimals": int(decimals),
        "show_legend": show_legend,
        "width": int(width),
        "height": int(height),
    },
)

# 可信度检查
metas = []
for sid in series_ids:
    m = repo.get_series(sid)
    if m is None:
        continue
    ind = repo.get_indicator(m["indicator_id"])
    metas.append({**m, **(ind.model_dump() if ind else {})})
cred = check_chart(spec, metas)
if cred.issues:
    st.subheader("⚠️ 图表可信度检查")
    render_quality_report(cred)
    proceed = st.checkbox("已知悉以上问题，仍然生成图表")
    if not proceed:
        st.stop()
else:
    st.success("可信度检查通过。")

data = prepare_series_data(repo, series_ids)
fig = build_figure(spec, data)
st.plotly_chart(fig, use_container_width=True)

chart_name = st.text_input("保存图表名称", spec.name)
if st.button("保存图表配置"):
    spec.name = chart_name
    cid = repo.save_chart(spec)
    st.success(f"已保存图表 #{cid}。")
