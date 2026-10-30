"""全局路径与常量配置。

所有路径都从源码位置动态推导，避免项目移动后遗留某台电脑的绝对路径。
项目根目录由本文件位置向上两级推导（macrosope/config.py -> 项目根）。
"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据目录：原始文件与数据库分离
DATA_DIR = Path(os.environ.get("MACROSOPE_DATA_DIR", PROJECT_ROOT / "data")).resolve()
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("MACROSOPE_DB_PATH", DATA_DIR / "macrosope.duckdb")).resolve()
EXPORT_DIR = DATA_DIR / "exports"

# 数据库 schema 版本，结构变更时 +1 并新增迁移
SCHEMA_VERSION = 2

# 支持的导入格式（第一版仅这四种）
SUPPORTED_FORMATS = ("csv", "xlsx", "json", "parquet")
REJECTED_FORMATS = ("xlsm", "xlsb")  # 拒绝含宏的 Excel

# 字段映射中的角色
FIELD_ROLES = (
    "date",       # 日期列
    "indicator",  # 指标名称列
    "value",      # 数值列
    "entity",     # 地区/实体列
    "unit",       # 单位列
    "frequency",  # 频率列
    "source",     # 数据来源列
    "note",       # 备注列
    "ignore",     # 忽略
)

# 频率
FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "annual")

# 频率到 pandas 周期/别名映射（用于重采样）
# 注意 pandas 3.0 已移除旧的 M/Q/Y 别名，改用 ME/QE/YE
FREQ_ALIAS = {
    "daily": "D",
    "weekly": "W",
    "monthly": "ME",
    "quarterly": "QE",
    "annual": "YE",
}

# 质量检查问题级别
LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"
LEVEL_INFO = "info"

# 研究项目条目的四类分层：原始事实 / 计算结果 / 用户推断 / 未验证假设
PROJECT_ENTRY_KINDS = ("fact", "calculation", "inference", "hypothesis")

# 频率聚合方法
AGG_METHODS = ("sum", "mean", "first", "last", "max", "min")


def ensure_dirs() -> None:
    """确保运行所需目录存在。"""
    for d in (DATA_DIR, RAW_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
