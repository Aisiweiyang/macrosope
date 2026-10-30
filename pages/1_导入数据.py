"""导入数据页：读取 → 设置 → 字段映射 → 指标元数据 → 落库。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
from macrosope.config import FIELD_ROLES, SUPPORTED_FORMATS
from macrosope.importers import (
    list_sheets,
    read_file,
)
from macrosope.mapping import suggest_roles
from macrosope.models import IndicatorMeta
from macrosope.services import ingest
from macrosope.ui import get_repo

repo = get_repo()

ROLE_LABELS = {
    "date": "日期",
    "indicator": "指标名称",
    "value": "数值",
    "entity": "地区/实体",
    "unit": "单位",
    "frequency": "频率",
    "source": "来源",
    "note": "备注",
    "ignore": "忽略",
}

st.title("📥 导入数据")
st.caption("支持 CSV / XLSX / JSON / Parquet。第一版不接 API、不爬取、不执行 Excel 宏（拒绝 XLSM）。")

UPLOAD_DIR = Path(tempfile.gettempdir()) / "macrosope_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _save_upload(uploaded) -> str:
    path = UPLOAD_DIR / uploaded.name
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    return str(path)


uploaded = st.file_uploader("选择数据文件", type=list(SUPPORTED_FORMATS))
path_input = st.text_input("或输入本地文件完整路径（可选）", "")

file_path: str | None = None
fmt: str | None = None
if uploaded is not None:
    file_path = _save_upload(uploaded)
    fmt = Path(uploaded.name).suffix.lower().lstrip(".")
elif path_input.strip():
    p = Path(path_input.strip())
    if p.exists():
        file_path = str(p)
        fmt = p.suffix.lower().lstrip(".")
    else:
        st.error(f"文件不存在：{path_input}")

if file_path is None:
    st.stop()

st.divider()

# ---------------- 读取设置 ----------------
with st.expander("读取设置", expanded=True):
    params: dict = {}
    if fmt == "csv":
        enc = st.selectbox("编码", ["自动", "utf-8-sig", "utf-8", "gb18030", "gbk", "big5"], index=0)
        delim = st.selectbox("分隔符", ["自动", ",", ";", "\\t", "|"], index=0)
        header_row = st.number_input("表头行（0 起，-1 表示无表头）", -1, 50, 0)
        skiprows = st.number_input("跳过顶部说明行数", 0, 100, 0)
        params = {
            "encoding": None if enc == "自动" else enc,
            "delimiter": None if delim == "自动" else ("\t" if delim == "\\t" else delim),
            "header_row": None if header_row < 0 else int(header_row),
            "skiprows": int(skiprows),
        }
    elif fmt == "xlsx":
        sheets = list_sheets(file_path)
        sheet = st.selectbox("工作表", sheets)
        header_row = st.number_input("表头行（0 起，-1 表示无表头）", -1, 50, 0)
        skiprows = st.number_input("跳过顶部说明行数", 0, 100, 0)
        params = {
            "sheet_name": sheet,
            "header_row": None if header_row < 0 else int(header_row),
            "skiprows": int(skiprows),
        }
    elif fmt == "json":
        orient = st.selectbox("JSON 结构", ["auto", "records", "columns", "index", "split", "table"])
        params = {"orient": None if orient == "auto" else orient}
    else:
        params = {}

    thousands = st.checkbox("去除千位分隔符", value=True)
    percent = st.checkbox("百分号转小数（% 除以 100）", value=True)
    date_format = st.text_input(
        "日期格式（可选）", "", help="留空自动解析；年份可填 %Y，紧凑日期可填 %Y%m%d。"
    )

preview = read_file(file_path, **params)
for issue in preview.issues:
    level = issue.get("level", "info")
    st.warning(f"[{level}] {issue.get('message')}" if level != "error" else f"❌ {issue.get('message')}")

df_raw = preview.df
st.subheader("数据预览")
st.dataframe(df_raw.head(100), use_container_width=True)

if df_raw.empty:
    st.stop()

# ---------------- 字段映射 ----------------
st.subheader("字段映射")
st.caption("自动识别仅为建议，请逐列确认角色后再导入。")
suggested = suggest_roles(df_raw)
roles: dict[str, str] = {}
for col in df_raw.columns:
    default_role = suggested.get(str(col), "ignore")
    idx = list(FIELD_ROLES).index(default_role) if default_role in FIELD_ROLES else 0
    roles[str(col)] = st.selectbox(
        f"列「{col}」的角色",
        options=list(FIELD_ROLES),
        index=idx,
        format_func=lambda r: ROLE_LABELS.get(r, r),
        key=f"role_{col}",
    )

# ---------------- 指标元数据模板 ----------------
with st.expander("指标元数据（应用到本次导入的所有指标）", expanded=True):
    c1, c2, c3 = st.columns(3)
    tpl_unit = c1.text_input("单位", "")
    tpl_freq = c2.selectbox("频率", ["", "daily", "weekly", "monthly", "quarterly", "annual"])
    tpl_region = c3.text_input("地区/实体", "")
    c1b, c2b, c3b = st.columns(3)
    tpl_currency = c1b.text_input("币种", "")
    tpl_source = c2b.text_input("来源机构", "")
    tpl_nom = c3b.selectbox("名义/实际", ["unknown", "nominal", "real"])
    c1c, c2c = st.columns(2)
    tpl_stock = c1c.selectbox("存量/流量", ["unknown", "stock", "flow"])
    tpl_cum = c2c.selectbox("当期/累计", ["unknown", "period", "cumulative"])
    dataset_name = st.text_input("数据集名称（可选）", Path(file_path).stem)

# ---------------- 导入 ----------------
if st.button("确认导入", type="primary"):
    template = IndicatorMeta(
        unit=tpl_unit,
        frequency=tpl_freq,
        region=tpl_region,
        currency=tpl_currency,
        source_org=tpl_source,
        nominal_or_real=tpl_nom,
        stock_or_flow=tpl_stock,
        period_or_cumulative=tpl_cum,
    )
    try:
        dataset_id, series_ids = ingest(
            repo,
            file_path,
            fmt or "",
            params,
            roles,
            template,
            numeric={"thousands": "," if thousands else None, "percent": percent},
            date_format=date_format.strip() or None,
            dataset_name=dataset_name or None,
        )
        st.success(f"导入成功：数据集 #{dataset_id}，创建 {len(series_ids)} 条序列。")
        st.info("可在左侧「数据质量检查」查看质量报告，或在「清洗与变换」开始处理。")
    except ValueError as exc:
        st.error(str(exc))
