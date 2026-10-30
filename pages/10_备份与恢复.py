"""备份与恢复页。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st
from macrosope.config import EXPORT_DIR
from macrosope.export import sanitize_filename
from macrosope.ui import get_repo

repo = get_repo()

st.title("💾 备份与恢复")

st.subheader("备份")
st.caption(f"将当前 DuckDB 数据库备份到 `{EXPORT_DIR}`。")
default_backup_name = f"宏观数据工作台备份_{datetime.now():%Y%m%d_%H%M%S}"
backup_name = st.text_input("备份文件名", default_backup_name)
if st.button("立即备份"):
    path = repo.backup(EXPORT_DIR / sanitize_filename(backup_name))
    st.success(f"已备份到 {path}")

st.divider()
st.subheader("恢复")
st.warning("恢复会替换当前数据库；系统会先自动创建恢复前备份，并在失败时回滚。")
path_input = st.text_input("要恢复的 .duckdb 文件完整路径", "")
backup_valid = False
src: Path | None = None
if path_input.strip():
    src = Path(path_input.strip())
    try:
        info = repo.validate_backup(src)
        backup_valid = True
        st.success(
            f"备份校验通过：schema v{info['schema_version']}，"
            f"包含 {info['table_count']} 张数据表。"
        )
    except ValueError as exc:
        st.error(str(exc))

confirm = st.checkbox("确认覆盖当前数据库并恢复")
if st.button("执行恢复", disabled=not (backup_valid and confirm)) and src is not None:
    try:
        pre_restore = repo.restore(src, backup_dir=EXPORT_DIR)
        st.success(f"恢复完成。恢复前数据库已自动备份到：{pre_restore}")
    except (OSError, ValueError) as exc:
        st.error(f"恢复失败，当前数据库未被替换：{exc}")
