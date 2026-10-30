"""宏观数据工作台 —— 首页。

首页只显示最近项目、最近数据集、质量提示与快速入口，不做信息过载的大屏。
"""
from __future__ import annotations

import streamlit as st
from macrosope import __app_name__, __version__
from macrosope.ui import get_repo

st.set_page_config(page_title=__app_name__, page_icon="📊", layout="wide")

repo = get_repo()

st.title(__app_name__)
st.caption(f"本地经济数据导入 · 处理 · 分析 · 制图　（v{__version__}）")

col1, col2 = st.columns(2)

with col1:
    st.subheader("最近项目")
    projects = repo.list_projects()[:5]
    if projects:
        for p in projects:
            st.markdown(f"- **{p['name']}**　`{p['research_question'] or ''}`")
    else:
        st.info("还没有研究项目。可在左侧「研究项目」页创建。")

with col2:
    st.subheader("最近数据集")
    datasets = repo.list_datasets()[:5]
    if datasets:
        for d in datasets:
            st.markdown(
                f"- **{d.name}**　`{d.source_format}`　{d.row_count} 行 × {d.column_count} 列"
            )
    else:
        st.info("还没有数据集。可在左侧「导入数据」页导入。")

st.divider()

st.subheader("快速入口")
st.markdown(
    """
    - 📥 **导入数据** —— 导入 CSV / XLSX / JSON / Parquet，确认字段映射后落库
    - 🧹 **清洗与变换** —— 同比、环比、指数化、移动平均、频率转换等（可撤销）
    - 📈 **图表生成器** —— 生成专业图表，生成前自动做可信度检查
    - 🗂️ **研究项目** —— 保存研究问题、数据、图表与笔记（事实/推断/假设分层）
    """
)

st.caption("数据全部保存在本地 DuckDB，不上传、不联网、不接 API。")
