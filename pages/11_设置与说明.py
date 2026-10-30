"""设置与使用说明页。"""
from __future__ import annotations

import streamlit as st
from macrosope import __version__
from macrosope.config import (
    DB_PATH,
    EXPORT_DIR,
    RAW_DIR,
    SCHEMA_VERSION,
    SUPPORTED_FORMATS,
)
from macrosope.transforms import TRANSFORM_DEFS
from macrosope.ui import get_repo

repo = get_repo()

st.title("⚙️ 设置与使用说明")

st.subheader("系统信息")
st.write(f"版本：{__version__}")
st.write(f"数据库 schema 版本：{SCHEMA_VERSION}（当前实际：{repo.schema_version()}）")
st.write(f"数据库文件：`{DB_PATH}`")
st.write(f"原始文件归档：`{RAW_DIR}`")
st.write(f"导出目录：`{EXPORT_DIR}`")

st.subheader("支持导入格式")
st.write("、".join(SUPPORTED_FORMATS))

st.subheader("使用流程")
st.markdown(
    """
    1. **导入数据**：上传文件 → 设置编码/分隔符/表头行 → 确认字段映射 → 填写指标元数据 → 导入
    2. **数据质量检查**：查看错误/警告/提示
    3. **清洗与变换**：同比、环比、指数化、移动平均、频率转换（可撤销）
    4. **图表生成器**：选序列 → 选类型 → 可信度检查 → 生成 → 保存
    5. **研究项目**：记录研究问题、数据、图表、笔记（事实/推断/假设分层）
    6. **导出中心**：导出数据、图表、配置、管道
    """
)

st.subheader("已实现的变换操作")
for op, d in sorted(TRANSFORM_DEFS.items()):
    st.markdown(f"- **{d.label}**（`{op}`）：{d.formula}")

st.subheader("设计原则")
st.markdown(
    """
    - 原始数据与派生数据分离，原始文件绝不覆盖
    - 所有变换可查看、可撤销、可重新运行
    - 质量检查只报告，绝不静默填充或删除
    - 不把相关关系自动解释成因果关系
    - 禁止把低频数据插值成伪造的高频数据
    """
)
