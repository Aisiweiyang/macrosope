"""数据集管理页：查看、删除数据集。"""
from __future__ import annotations

import streamlit as st
from macrosope.ui import get_repo

repo = get_repo()

st.title("🗃️ 数据集管理")

datasets = repo.list_datasets()
if not datasets:
    st.info("还没有数据集，请先到「导入数据」页导入。")
    st.stop()

for d in datasets:
    with st.expander(f"{d.name}（{d.source_format} · {d.row_count} 行）"):
        st.write(f"来源文件：`{d.source_filename}`")
        st.write(f"归档原始文件：`{d.raw_path}`")
        st.write(f"导入参数：`{d.import_params}`")
        mappings = repo.get_field_mappings(d.dataset_id)
        if mappings:
            st.write("字段映射：", ", ".join(f"{m.column}→{m.role}" for m in mappings))

        impact = repo.dataset_impact(d.dataset_id)
        st.caption(
            "关联范围："
            f"{impact['series']} 条序列、{impact['observations']} 个观测值、"
            f"{impact['steps']} 个变换步骤、{impact['charts']} 张图表。"
        )
        delete_mode = st.radio(
            "删除方式",
            ["仅删除数据集记录（保留序列）", "删除数据集及其关联序列"],
            key=f"mode_{d.dataset_id}",
        )
        delete_series = delete_mode == "删除数据集及其关联序列"
        if delete_series:
            st.warning("关联观测值、变换步骤和图表配置也会一并删除；原始归档文件仍保留。")
        confirm = st.checkbox(
            f"我确认删除数据集“{d.name}”",
            key=f"confirm_{d.dataset_id}",
        )
        if st.button(
            "确认删除",
            key=f"delete_{d.dataset_id}",
            type="primary",
            disabled=not confirm,
        ):
            deleted = repo.delete_dataset(d.dataset_id, delete_series=delete_series)
            if delete_series:
                st.warning(
                    f"已删除数据集及 {deleted['series']} 条关联序列；原始归档文件已保留。"
                )
            else:
                st.success("已删除数据集记录，关联序列已保留并解除来源关联。")
            st.rerun()
