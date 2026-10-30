"""中国经济交换快照：离线发现、只读预览、确认和事务导入。"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from macrosope.services import (
    default_exchange_directory,
    discover_exchange_file,
    import_exchange,
    preview_exchange,
)
from macrosope.ui import get_repo

repo = get_repo()
st.title("🇨🇳 中国经济数据")
st.caption("只读取本地交换文件；本页不访问 HTTP/HTTPS、不调用外部 API，也不补采官方数据。")

if "china_economy_directory" not in st.session_state:
    st.session_state.china_economy_directory = str(default_exchange_directory())

directory = st.text_input(
    "交换文件目录",
    key="china_economy_directory",
    help="默认值按“中国经济分析”和“数据分析”的同级关系动态推导，可修改。",
)

if st.button("发现最新文件", type="primary"):
    try:
        selected = discover_exchange_file(directory)
        st.session_state.china_economy_preview = preview_exchange(selected, repo)
    except (OSError, ValueError) as exc:
        st.session_state.pop("china_economy_preview", None)
        st.error(str(exc))

preview = st.session_state.get("china_economy_preview")
if preview is None:
    st.info("请选择目录并点击“发现最新文件”。新版交换文件优先；没有新版时会在内存中适配最新旧版 JSON。")
    st.stop()

payload = preview.payload
st.subheader("只读预览")
st.write(f"文件路径：`{preview.path}`")
top = pd.DataFrame(
    [
        {
            "schema_version": payload["schema_version"],
            "snapshot_id": payload["snapshot_id"],
            "content_hash": payload["content_hash"],
            "file_sha256": preview.identity.file_sha256,
            "generated_at": payload["generated_at"],
            "文件大小": preview.identity.size,
            "指标数量": len(preview.indicators),
            "观测值数量": len(payload["observations"]),
        }
    ]
)
st.dataframe(top, width="stretch", hide_index=True)
st.dataframe(pd.DataFrame(preview.indicators), width="stretch", hide_index=True)

if preview.warnings:
    with st.expander(f"警告和缺失信息（{len(preview.warnings)}）", expanded=True):
        for warning in preview.warnings:
            st.warning(warning)

differences = preview.differences
st.subheader("历史差异")
counts = pd.DataFrame(
    [
        {
            "全新指标": differences["new_indicator_count"],
            "全新日期": differences["new_date_count"],
            "完全重复": differences["duplicate_count"],
            "历史数值修订": differences["revision_count"],
        }
    ]
)
st.dataframe(counts, width="stretch", hide_index=True)
if differences["new_indicators"]:
    st.info("全新指标：" + "、".join(differences["new_indicators"]))
if differences["new_dates"]:
    with st.expander("全新日期明细"):
        st.dataframe(pd.DataFrame(differences["new_dates"]), width="stretch", hide_index=True)
if differences["revisions"]:
    st.warning("历史修订将作为新的不可变快照导入，不会覆盖旧值。")
    st.dataframe(pd.DataFrame(differences["revisions"]), width="stretch", hide_index=True)

with st.expander("分析快照说明"):
    st.markdown(
        "`dimensions`、`cycle`、`drivers`、`risks`、`correlation`、`balances`、`breadth` "
        "将作为数据集附带的分析快照保存，属于自动计算、风险提示或模型推断，不写入原始指标事实。"
    )
    st.warning("相关不代表因果；周期定位是指标框架，不是确定性预测。")

confirmed = st.checkbox("我已检查预览和历史修订")
if st.button("确认导入", disabled=not confirmed, type="primary"):
    try:
        result = import_exchange(repo, preview)
    except Exception as exc:  # noqa: BLE001 - 页面必须展示事务失败原因
        st.error(str(exc))
    else:
        if result.duplicate_snapshot:
            st.info(f"完全重复，未再次写入。原数据集 #{result.dataset_id}。")
        else:
            st.success(f"导入成功：数据集 #{result.dataset_id}")
        st.json(
            {
                "dataset_id": result.dataset_id,
                "series_ids": result.series_ids,
                "写入观测值": result.observation_count,
                "跳过数量": result.skipped_count,
                "全新指标数量": result.new_indicator_count,
                "全新日期数量": result.new_date_count,
                "重复数量": result.duplicate_count,
                "修订数量": result.revision_count,
                "原始文件归档位置": result.archived_file,
            }
        )
