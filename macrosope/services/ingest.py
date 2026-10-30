"""数据导入落库服务。

把原始文件读入、数值规范化、字段映射、日期解析、拆分序列并写入 DuckDB。
原始文件归档到 data/raw，绝不覆盖；派生数据与原始数据分离（is_derived 标记）。
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from macrosope.db import Repository
from macrosope.export import safe_join, sanitize_filename
from macrosope.importers import normalize_dataframe, read_file
from macrosope.mapping import to_long
from macrosope.models import DatasetMeta, FieldMapping, IndicatorMeta

# 标准长表列
_STD_COLS = ["date", "entity", "indicator", "value", "unit", "frequency", "source", "note"]


def standardize_long(df: pd.DataFrame, roles: dict[str, str]) -> pd.DataFrame:
    """把确认过角色映射的 DataFrame 转成标准长表。"""
    col_of: dict[str, str] = {}
    for c, r in roles.items():
        if r != "ignore":
            col_of.setdefault(r, str(c))

    # 宽表：无 indicator 列，按数值列 melt
    if "indicator" not in col_of:
        return to_long(df, roles)

    rename = {col_of[r]: std for std, r in
              [("date", "date"), ("entity", "entity"), ("indicator", "indicator"),
               ("value", "value"), ("unit", "unit"), ("frequency", "frequency"),
               ("source", "source"), ("note", "note")] if r in col_of}
    keep = list(rename.keys())
    return df[keep].rename(columns=rename)


def _archive_raw(file_path: str, raw_dir: str | Path) -> str:
    """唯一归档原始文件，使用排他创建确保绝不覆盖。"""
    src = Path(file_path)
    if not src.is_file():
        raise ValueError(f"原始文件不存在：{src}")
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = sanitize_filename(src.name)
    dest = safe_join(raw_dir, f"{stamp}_{uuid4().hex[:8]}_{safe_name}")
    with src.open("rb") as source_handle, dest.open("xb") as target_handle:
        shutil.copyfileobj(source_handle, target_handle)
    shutil.copystat(src, dest)
    return str(dest)


def ingest(
    repo: Repository,
    file_path: str,
    source_format: str,
    import_params: dict,
    roles: dict[str, str],
    template: IndicatorMeta,
    numeric: dict | None = None,
    date_format: str | None = None,
    dataset_name: str | None = None,
) -> tuple[int, list[int]]:
    """执行完整导入，返回 (dataset_id, 新建序列 id 列表)。"""
    numeric = numeric or {"thousands": ",", "percent": True}

    # 1. 读取
    preview = read_file(file_path, **import_params)

    # 2. 数值规范化
    df, _conversions = normalize_dataframe(
        preview.df,
        thousands_sep=numeric.get("thousands"),
        percent=numeric.get("percent", True),
    )

    # 3. 字段映射 -> 标准长表
    long = standardize_long(df, roles)

    # 4. 日期解析（错误必须处理，不得静默丢弃）
    raw_dates = long["date"]
    n_missing_date = int(raw_dates.isna().sum())
    if n_missing_date > 0:
        raise ValueError(f"日期列有 {n_missing_date} 个缺失值，请先补充或明确处理")
    # 数字年份/紧凑日期按日历文本解析，避免被 pandas 当作 Unix 纳秒时间戳。
    date_input = raw_dates.astype(str) if pd.api.types.is_numeric_dtype(raw_dates) else raw_dates
    parsed = pd.to_datetime(date_input, format=date_format or None, errors="coerce")
    n_bad = int((raw_dates.notna() & parsed.isna()).sum())
    if n_bad > 0:
        sample = raw_dates[raw_dates.notna() & parsed.isna()].head(5).astype(str).tolist()
        raise ValueError(
            f"有 {n_bad} 个日期无法解析，请调整日期格式。示例：{sample}"
        )
    long["date"] = parsed

    # 5. 数值列强制为 float，非数字值报错
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    n_nonnum = int(long["value"].isna().sum())
    if n_nonnum > 0:
        raise ValueError(f"数值列有 {n_nonnum} 个非数字值，请先清洗")

    # 6. 拆分并完整校验所有待写入序列（此阶段不写数据库）
    series_payloads: list[dict] = []
    group_keys = ["indicator"] + (["entity"] if "entity" in long.columns else [])
    for key, grp in long.groupby(group_keys, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        indicator_name = key[0]
        entity_value = key[1] if len(key) > 1 else ""
        entity = "" if pd.isna(entity_value) else str(entity_value)
        # 单位/频率/来源优先取该组的第一条记录，否则用模板
        unit = _first(grp, "unit") or template.unit
        frequency = _first(grp, "frequency") or template.frequency
        source_org = _first(grp, "source") or template.source_org

        meta = template.model_copy(update={
            "name": str(indicator_name),
            "unit": unit,
            "frequency": frequency,
            "source_org": source_org,
            "region": template.region or entity,
        })
        obs = grp[["date", "value"]].dropna(subset=["value"])
        duplicate_dates = obs["date"].duplicated(keep=False)
        if duplicate_dates.any():
            samples = (
                obs.loc[duplicate_dates, "date"].head(5).astype(str).tolist()
            )
            raise ValueError(
                f"序列“{indicator_name}”存在重复日期，请明确处理后再导入。示例：{samples}"
            )
        series_payloads.append({
            "indicator": meta,
            "series": {
                "entity": entity,
                "unit": unit,
                "frequency": frequency,
                "currency": template.currency,
            },
            "observations": obs,
        })

    # 7. 唯一归档原始文件
    raw_path = _archive_raw(file_path, Path(repo.db_path).parent / "raw")

    # 8. 数据集记录
    dataset_meta = DatasetMeta(
        name=dataset_name or Path(file_path).stem,
        source_filename=Path(file_path).name,
        source_format=source_format,
        import_params={**import_params, "numeric": numeric, "date_format": date_format},
        row_count=len(df),
        column_count=len(df.columns),
        raw_path=raw_path,
    )
    mappings = [
        FieldMapping(column=str(column), role=role)
        for column, role in roles.items()
    ]
    try:
        return repo.import_dataset_bundle(dataset_meta, mappings, series_payloads)
    except Exception:
        # 数据库事务已回滚；同步删除本次新建的归档副本，原始源文件不受影响。
        Path(raw_path).unlink(missing_ok=True)
        raise


def _first(grp: pd.DataFrame, col: str) -> str:
    if col not in grp.columns:
        return ""
    vals = grp[col].dropna().astype(str).unique()
    return vals[0] if len(vals) else ""
