"""数据库 DDL 与迁移。

schema_version 表记录当前版本；结构变更时在 MIGRATIONS 中追加对应版本的处理。
"""
from __future__ import annotations

SCHEMA_DDL = """
-- 数据库版本
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP
);

-- 数据集（导入结果元数据）
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    source_filename VARCHAR,
    source_format VARCHAR,
    import_params VARCHAR,
    row_count INTEGER,
    column_count INTEGER,
    created_at TIMESTAMP,
    raw_path VARCHAR
);

-- 字段映射（列 -> 长表角色）
CREATE TABLE IF NOT EXISTS field_mappings (
    dataset_id INTEGER,
    column_name VARCHAR,
    role VARCHAR,
    PRIMARY KEY (dataset_id, column_name)
);

-- 指标元数据
CREATE TABLE IF NOT EXISTS indicators (
    indicator_id INTEGER PRIMARY KEY,
    name VARCHAR,
    code VARCHAR,
    definition VARCHAR,
    unit VARCHAR,
    frequency VARCHAR,
    region VARCHAR,
    currency VARCHAR,
    source_org VARCHAR,
    source_link VARCHAR,
    updated_at VARCHAR,
    nominal_or_real VARCHAR,
    stock_or_flow VARCHAR,
    period_or_cumulative VARCHAR,
    seasonally_adjusted VARCHAR,
    base_period VARCHAR,
    scope_note VARCHAR,
    user_note VARCHAR
);

-- 序列（指标 × 实体/地区 × 口径）
CREATE TABLE IF NOT EXISTS series (
    series_id INTEGER PRIMARY KEY,
    indicator_id INTEGER,
    entity VARCHAR,
    unit VARCHAR,
    frequency VARCHAR,
    currency VARCHAR,
    is_derived BOOLEAN DEFAULT FALSE,
    source_dataset_id INTEGER,
    created_at TIMESTAMP
);

-- 观测值（长表）
CREATE TABLE IF NOT EXISTS observations (
    series_id INTEGER,
    date DATE,
    value DOUBLE,
    PRIMARY KEY (series_id, date)
);

-- 变换步骤
CREATE TABLE IF NOT EXISTS transform_steps (
    step_id INTEGER PRIMARY KEY,
    op_type VARCHAR,
    params VARCHAR,
    formula VARCHAR,
    description VARCHAR,
    input_series VARCHAR,
    output_series VARCHAR,
    seq INTEGER,
    created_at TIMESTAMP
);

-- 图表配置
CREATE TABLE IF NOT EXISTS charts (
    chart_id INTEGER PRIMARY KEY,
    name VARCHAR,
    chart_type VARCHAR,
    config VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 研究项目
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    research_question VARCHAR,
    notes VARCHAR,
    data_limitations VARCHAR,
    sources VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 项目条目（事实/计算/推断/假设 四类分层）
CREATE TABLE IF NOT EXISTS project_entries (
    entry_id INTEGER PRIMARY KEY,
    project_id INTEGER,
    kind VARCHAR,
    content VARCHAR,
    created_at TIMESTAMP
);

-- 项目-数据集关联
CREATE TABLE IF NOT EXISTS project_datasets (
    project_id INTEGER,
    dataset_id INTEGER,
    PRIMARY KEY (project_id, dataset_id)
);

-- 项目-图表关联
CREATE TABLE IF NOT EXISTS project_charts (
    project_id INTEGER,
    chart_id INTEGER,
    PRIMARY KEY (project_id, chart_id)
);

-- 中国经济交换文件导入审计（数据事实事务之外保留）
CREATE TABLE IF NOT EXISTS import_audits (
    audit_id INTEGER PRIMARY KEY,
    provider VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    snapshot_id VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    file_sha256 VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    archived_file VARCHAR,
    generated_at VARCHAR,
    imported_at TIMESTAMP,
    dataset_id INTEGER,
    import_status VARCHAR NOT NULL,
    warning_summary VARCHAR
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_import_audits_content_hash
ON import_audits(content_hash);

-- 自动计算与模型推断单独保存，不混入 observations 数据事实
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    dataset_id INTEGER NOT NULL,
    snapshot_id VARCHAR NOT NULL,
    generated_at VARCHAR,
    analysis_json VARCHAR NOT NULL,
    created_at TIMESTAMP,
    PRIMARY KEY (dataset_id, snapshot_id)
);
"""

# 迁移：key 为目标版本号，value 为执行该迁移的 SQL（在新库上从 0 逐个执行）
MIGRATIONS: dict[int, str] = {
    2: """
        CREATE TABLE IF NOT EXISTS import_audits (
            audit_id INTEGER PRIMARY KEY,
            provider VARCHAR NOT NULL,
            schema_version VARCHAR NOT NULL,
            snapshot_id VARCHAR NOT NULL,
            content_hash VARCHAR NOT NULL,
            file_sha256 VARCHAR NOT NULL,
            source_file VARCHAR NOT NULL,
            archived_file VARCHAR,
            generated_at VARCHAR,
            imported_at TIMESTAMP,
            dataset_id INTEGER,
            import_status VARCHAR NOT NULL,
            warning_summary VARCHAR
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_import_audits_content_hash
        ON import_audits(content_hash);
        CREATE TABLE IF NOT EXISTS analysis_snapshots (
            dataset_id INTEGER NOT NULL,
            snapshot_id VARCHAR NOT NULL,
            generated_at VARCHAR,
            analysis_json VARCHAR NOT NULL,
            created_at TIMESTAMP,
            PRIMARY KEY (dataset_id, snapshot_id)
        );
    """,
}
