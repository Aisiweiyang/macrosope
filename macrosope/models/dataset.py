"""数据集与字段映射模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FieldMapping(BaseModel):
    """一列数据在长表语义中的角色。"""

    column: str
    role: str  # 见 config.FIELD_ROLES


class DatasetMeta(BaseModel):
    """一次导入产生的数据集元数据。"""

    dataset_id: int | None = None
    name: str = ""
    source_filename: str = ""
    source_format: str = ""  # csv/xlsx/json/parquet
    import_params: dict = Field(default_factory=dict)  # 编码、分隔符、表头行等
    row_count: int = 0
    column_count: int = 0
    created_at: str = ""
    raw_path: str = ""  # 原始文件在 data/raw 下的归档路径
