"""清洗与变换页：应用变换 + 查看可撤销管道。"""
from __future__ import annotations

import json

import streamlit as st
from macrosope.transforms import TRANSFORM_DEFS
from macrosope.ui import get_pipeline, get_repo, series_options

repo = get_repo()
pipeline = get_pipeline()

st.title("🧹 清洗与变换")
st.caption("所有变换都记录为可查看、可撤销、可重新运行的步骤。")

TWO_INPUT_OPS = {"growth_contribution", "per_capita", "nominal_to_real"}

OP_GROUPS = {
    "清洗": ["sort_by_date", "drop_duplicates", "unit_convert", "fill_missing", "manual_edit"],
    "增长率": ["yoy", "mom", "annualized_mom", "period_change", "log_diff"],
    "累计/当期": ["cumulative_to_period", "period_to_cumulative"],
    "指数化": ["index_to_date", "index_first", "index_year_avg"],
    "移动统计": ["moving_average", "moving_median", "rolling_volatility"],
    "标准化": ["zscore", "minmax", "percentile_rank"],
    "结构": ["share", "structure_change"],
    "双序列": ["growth_contribution", "per_capita", "nominal_to_real"],
    "频率转换": ["resample"],
}

PARAM_SPECS: dict[str, list[tuple[str, str, str, object, object]]] = {
    "yoy": [("freq", "select", "频率", "monthly", ["daily", "weekly", "monthly", "quarterly", "annual"])],
    "annualized_mom": [("periods_per_year", "number", "每年期数", 12, None)],
    "period_change": [("periods", "number", "期数", 12, None)],
    "log_diff": [("scale", "number", "缩放系数", 100.0, None)],
    "index_to_date": [("base_date", "text", "基期日期", "", None)],
    "index_year_avg": [("base_year", "number", "基期年度", 2020, None)],
    "moving_average": [("window", "number", "窗口", 3, None)],
    "moving_median": [("window", "number", "窗口", 3, None)],
    "rolling_volatility": [("window", "number", "窗口", 3, None)],
    "unit_convert": [("factor", "number", "系数", 1.0, None)],
    "fill_missing": [("method", "select", "方法", "keep", ["keep", "drop", "ffill", "interp"])],
    "manual_edit": [("edits", "json", '编辑列表 [{"date":"2024-01","value":1}]', "[]", None)],
    "resample": [
        ("to_freq", "select", "目标频率", "quarterly", ["quarterly", "annual"]),
        ("method", "select", "聚合方法", "sum", ["sum", "mean", "first", "last", "max", "min"]),
    ],
}

opts = series_options(repo)
if not opts:
    st.info("还没有序列，请先导入数据。")
    st.stop()

group = st.selectbox("变换类别", list(OP_GROUPS.keys()))
op_type = st.selectbox(
    "变换操作",
    OP_GROUPS[group],
    format_func=lambda o: f"{TRANSFORM_DEFS[o].label}（{o}）",
)

# 展示变换元数据
d = TRANSFORM_DEFS[op_type]
with st.expander("公式与说明", expanded=True):
    st.markdown(f"**公式**：{d.formula}")
    st.markdown(f"**输入**：{d.input_fields}")
    st.markdown(f"**输出单位**：{d.output_unit}　|　**输出频率**：{d.output_frequency}")
    st.markdown(f"**缺失值处理**：{d.missing_handling}")
    if d.applicability:
        st.markdown(f"**适用条件**：{d.applicability}")
    st.markdown(f"**局限性**：{d.limitations}")

# 输入序列
if op_type in TWO_INPUT_OPS:
    labels = st.multiselect("选择输入序列（需 2 个）", list(opts.keys()), max_selections=2)
    input_ids = [opts[lab] for lab in labels]
else:
    label = st.selectbox("选择输入序列", list(opts.keys()))
    input_ids = [opts[label]]

# 参数
params: dict = {}
for key, kind, plabel, default, options in PARAM_SPECS.get(op_type, []):
    if kind == "select":
        params[key] = st.selectbox(plabel, options, index=options.index(default) if default in options else 0)
    elif kind == "number":
        params[key] = st.number_input(plabel, value=float(default) if isinstance(default, (int, float)) else 0.0)
    elif kind == "text":
        params[key] = st.text_input(plabel, str(default))
    elif kind == "json":
        raw = st.text_area(plabel, str(default), height=80)
        try:
            params[key] = json.loads(raw)
        except json.JSONDecodeError:
            st.error("JSON 格式有误")

if op_type == "fill_missing" and params.get("method") in ("ffill", "interp"):
    st.warning("前向填充/插值会制造不存在的值，可能造成数据失真。此操作由你主动选择。")

output_name = st.text_input("输出指标名称（可选，留空自动命名）", "")

if st.button("执行变换", type="primary"):
    if len(input_ids) < (2 if op_type in TWO_INPUT_OPS else 1):
        st.error("请选择足够的输入序列")
    else:
        try:
            new_ids = pipeline.apply(
                op_type, input_ids, params,
                output_name=output_name or None,
            )
            st.success(f"已创建派生序列 #{new_ids}。")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

st.divider()
st.subheader("变换管道（历史步骤）")
steps = repo.list_steps()
if not steps:
    st.info("还没有变换步骤。")
else:
    for s in steps:
        with st.expander(f"#{s.step_id} {s.op_type}　{s.created_at}"):
            st.markdown(f"**说明**：{s.description}")
            st.markdown(f"**公式**：{s.formula}")
            st.markdown(f"**输入序列**：{s.input_series} → **输出序列**：{s.output_series}")
            c1, c2 = st.columns(2)
            if c1.button("撤销（删除输出）", key=f"undo_{s.step_id}"):
                pipeline.undo(s.step_id)
                st.warning("已撤销。")
                st.rerun()
            if c2.button("重新运行", key=f"rerun_{s.step_id}"):
                pipeline.rerun(s.step_id)
                st.success("已重新运行。")
