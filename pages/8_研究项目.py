"""研究项目页：项目 + 事实/计算/推断/假设四类条目分层。"""
from __future__ import annotations

import streamlit as st
from macrosope.config import PROJECT_ENTRY_KINDS
from macrosope.projects import ProjectManager
from macrosope.ui import get_repo, series_options

repo = get_repo()
pm = ProjectManager(repo)

st.title("🗂️ 研究项目")

KIND_LABELS = {
    "fact": "原始事实",
    "calculation": "计算结果",
    "inference": "用户推断",
    "hypothesis": "未验证假设",
}

# 新建项目
with st.expander("新建项目", expanded=True):
    name = st.text_input("项目名称", "")
    question = st.text_input("研究问题", "")
    if st.button("创建项目") and name:
        pid = repo.create_project(name, question)
        st.success(f"已创建项目 #{pid}")
        st.rerun()

projects = repo.list_projects()
if not projects:
    st.info("还没有项目。")
    st.stop()

proj_names = {f"#{p['project_id']} {p['name']}": p["project_id"] for p in projects}
selected = st.selectbox("选择项目", list(proj_names.keys()))
project_id = proj_names[selected]

view = pm.full_view(project_id)
project = view["project"]

st.subheader(project["name"])
st.caption(project["research_question"] or "（无研究问题）")

c1, c2 = st.columns(2)
notes = c1.text_area("研究笔记", project["notes"] or "", height=120)
limitations = c2.text_area("数据限制", project["data_limitations"] or "", height=120)
sources = st.text_area("数据来源", project["sources"] or "", height=80)
if st.button("保存项目信息"):
    repo.update_project(
        project_id, project["name"], project["research_question"],
        notes, limitations, sources,
    )
    st.success("已保存")

st.divider()
st.subheader("条目（按性质分层）")
col1, col2 = st.columns([2, 3])
with col1:
    kind = st.selectbox("条目类型", list(PROJECT_ENTRY_KINDS), format_func=lambda k: KIND_LABELS[k])
    content = st.text_area("内容", height=120)
    if st.button("添加条目") and content:
        pm.add_entry(project_id, kind, content)
        st.rerun()

with col2:
    for k in PROJECT_ENTRY_KINDS:
        entries = view["entries"].get(k, [])
        if entries:
            st.markdown(f"**{KIND_LABELS[k]}（{len(entries)}）**")
            for e in entries:
                st.markdown(f"- {e['content']}")

st.divider()
st.subheader("关联数据与图表")
sopts = series_options(repo)
sopts = {v: k for k, v in sopts.items()}  # series_id -> label
chart_names = {c.chart_id: c.name for c in repo.list_charts()}
c1, c2 = st.columns(2)
with c1:
    ds = repo.list_datasets()
    dnames = {f"{d.name}": d.dataset_id for d in ds}
    sel_ds = st.multiselect("关联数据集", list(dnames.keys()), default=[
        f for f, i in dnames.items() if i in view["dataset_ids"]
    ])
    if st.button("更新数据集关联"):
        # 简化：追加新选中的
        for f in sel_ds:
            repo.link_project_dataset(project_id, dnames[f])
        st.success("已更新")
with c2:
    cnames = {f"#{cid} {chart_names.get(cid, '')}": cid for cid in chart_names}
    sel_ch = st.multiselect("关联图表", list(cnames.keys()), default=[
        f for f, i in cnames.items() if i in view["chart_ids"]
    ])
    if st.button("更新图表关联"):
        for f in sel_ch:
            repo.link_project_chart(project_id, cnames[f])
        st.success("已更新")
