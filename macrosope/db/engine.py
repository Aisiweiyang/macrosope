"""DuckDB 仓储层。

所有持久化读写都通过 Repository 完成。每个方法打开一个短连接，
避免 Streamlit 多线程下的连接竞争。ID 用 max+1 显式生成，便于单机本地使用。
"""
from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from macrosope.config import SCHEMA_VERSION, ensure_dirs
from macrosope.db.schema import MIGRATIONS, SCHEMA_DDL
from macrosope.models import (
    ChartSpec,
    DatasetMeta,
    FieldMapping,
    IndicatorMeta,
    TransformStep,
)

_REQUIRED_TABLES = {
    "schema_version",
    "datasets",
    "field_mappings",
    "indicators",
    "series",
    "observations",
    "transform_steps",
    "charts",
    "projects",
    "project_entries",
    "project_datasets",
    "project_charts",
    "import_audits",
    "analysis_snapshots",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _loads(s: str | None, default):
    if s is None or s == "":
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


class Repository:
    """DuckDB 持久化仓储。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        from macrosope.config import DB_PATH

        ensure_dirs()
        self.db_path = str(db_path or DB_PATH)
        self.migrate()

    # ------------------------------------------------------------------ 连接
    @contextmanager
    def _conn(self) -> Iterator[duckdb.DuckDBPyConnection]:
        conn = duckdb.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ 迁移
    def migrate(self) -> None:
        with self._conn() as conn:
            conn.execute(SCHEMA_DDL)
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()
            current = int(row[0]) if row is not None else 0
            for target in sorted(MIGRATIONS):
                if target > current:
                    conn.execute(MIGRATIONS[target])
            if current < SCHEMA_VERSION:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    [SCHEMA_VERSION, _now()],
                )

    def schema_version(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()
            return int(row[0]) if row is not None else 0

    # ------------------------------------------------------------------ 通用
    def _next_id(self, conn: duckdb.DuckDBPyConnection, table: str, col: str) -> int:
        row = conn.execute(f"SELECT COALESCE(MAX({col}), 0) + 1 FROM {table}").fetchone()
        return int(row[0]) if row is not None else 1

    # ------------------------------------------------------------------ 数据集
    def create_dataset(self, meta: DatasetMeta) -> int:
        with self._conn() as conn:
            did = self._next_id(conn, "datasets", "dataset_id")
            conn.execute(
                """
                INSERT INTO datasets
                (dataset_id, name, source_filename, source_format, import_params,
                 row_count, column_count, created_at, raw_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    did,
                    meta.name,
                    meta.source_filename,
                    meta.source_format,
                    _dumps(meta.import_params),
                    meta.row_count,
                    meta.column_count,
                    _now(),
                    meta.raw_path,
                ],
            )
            return did

    def list_datasets(self) -> list[DatasetMeta]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM datasets ORDER BY created_at DESC"
            ).fetchdf()
        return [self._row_to_dataset(r) for r in df.to_dict("records")]

    def get_dataset(self, dataset_id: int) -> DatasetMeta | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM datasets WHERE dataset_id = ?", [dataset_id]
            ).fetchdf()
        if df.empty:
            return None
        return self._row_to_dataset(df.to_dict("records")[0])

    def import_dataset_bundle(
        self,
        meta: DatasetMeta,
        mappings: list[FieldMapping],
        series_payloads: list[dict],
        *,
        analysis_snapshot: dict | None = None,
    ) -> tuple[int, list[int]]:
        """在一个事务中写入数据集、字段映射、指标、序列、观测值和分析快照。"""
        with self._conn() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                dataset_id = self._next_id(conn, "datasets", "dataset_id")
                conn.execute(
                    """
                    INSERT INTO datasets
                    (dataset_id, name, source_filename, source_format, import_params,
                     row_count, column_count, created_at, raw_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        dataset_id,
                        meta.name,
                        meta.source_filename,
                        meta.source_format,
                        _dumps(meta.import_params),
                        meta.row_count,
                        meta.column_count,
                        _now(),
                        meta.raw_path,
                    ],
                )

                for mapping in mappings:
                    conn.execute(
                        "INSERT INTO field_mappings "
                        "(dataset_id, column_name, role) VALUES (?, ?, ?)",
                        [dataset_id, mapping.column, mapping.role],
                    )

                series_ids: list[int] = []
                for payload in series_payloads:
                    indicator: IndicatorMeta = payload["indicator"]
                    indicator_id = self._next_id(conn, "indicators", "indicator_id")
                    conn.execute(
                        """
                        INSERT INTO indicators
                        (indicator_id, name, code, definition, unit, frequency, region,
                         currency, source_org, source_link, updated_at, nominal_or_real,
                         stock_or_flow, period_or_cumulative, seasonally_adjusted,
                         base_period, scope_note, user_note)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            indicator_id,
                            indicator.name,
                            indicator.code,
                            indicator.definition,
                            indicator.unit,
                            indicator.frequency,
                            indicator.region,
                            indicator.currency,
                            indicator.source_org,
                            indicator.source_link,
                            indicator.updated_at,
                            indicator.nominal_or_real,
                            indicator.stock_or_flow,
                            indicator.period_or_cumulative,
                            indicator.seasonally_adjusted,
                            indicator.base_period,
                            indicator.scope_note,
                            indicator.user_note,
                        ],
                    )

                    series_meta = payload["series"]
                    series_id = self._next_id(conn, "series", "series_id")
                    conn.execute(
                        """
                        INSERT INTO series
                        (series_id, indicator_id, entity, unit, frequency, currency,
                         is_derived, source_dataset_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            series_id,
                            indicator_id,
                            series_meta.get("entity", ""),
                            series_meta.get("unit", ""),
                            series_meta.get("frequency", ""),
                            series_meta.get("currency", ""),
                            False,
                            dataset_id,
                            _now(),
                        ],
                    )

                    observations: pd.DataFrame = payload["observations"]
                    rows = [
                        (series_id, _to_date(row["date"]), float(row["value"]))
                        for row in observations.to_dict("records")
                        if pd.notna(row["value"])
                    ]
                    if rows:
                        conn.executemany(
                            "INSERT INTO observations (series_id, date, value) "
                            "VALUES (?, ?, ?)",
                            rows,
                        )
                    series_ids.append(series_id)

                if analysis_snapshot is not None:
                    conn.execute(
                        """
                        INSERT INTO analysis_snapshots
                        (dataset_id, snapshot_id, generated_at, analysis_json, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        [
                            dataset_id,
                            analysis_snapshot["snapshot_id"],
                            analysis_snapshot.get("generated_at"),
                            _dumps(analysis_snapshot.get("analysis", {})),
                            _now(),
                        ],
                    )

                conn.execute("COMMIT")
                return dataset_id, series_ids
            except Exception:
                conn.execute("ROLLBACK")
                raise

    # -------------------------------------------------------- 交换文件审计/历史
    def get_import_audit(self, content_hash: str) -> dict | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM import_audits WHERE content_hash = ?", [content_hash]
            ).fetchdf()
        if df.empty:
            return None
        row = df.to_dict("records")[0]
        for key in ("audit_id", "dataset_id"):
            if row.get(key) is not None and not pd.isna(row[key]):
                row[key] = int(row[key])
            elif key == "dataset_id":
                row[key] = None
        return row

    def begin_import_audit(self, record: dict) -> int:
        """独立事务记录 pending；rolled_back 的同一内容允许显式重试。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT audit_id, import_status FROM import_audits WHERE content_hash = ?",
                [record["content_hash"]],
            ).fetchone()
            if row is not None:
                audit_id, status = int(row[0]), str(row[1])
                if status == "success":
                    return audit_id
                conn.execute(
                    """
                    UPDATE import_audits SET provider=?, schema_version=?, snapshot_id=?,
                        file_sha256=?, source_file=?, archived_file=?, generated_at=?,
                        imported_at=?, dataset_id=NULL, import_status='pending', warning_summary=?
                    WHERE audit_id=?
                    """,
                    [
                        record["provider"], record["schema_version"], record["snapshot_id"],
                        record["file_sha256"], record["source_file"],
                        record.get("archived_file"), record.get("generated_at"), _now(),
                        record.get("warning_summary", ""), audit_id,
                    ],
                )
                return audit_id
            audit_id = self._next_id(conn, "import_audits", "audit_id")
            conn.execute(
                """
                INSERT INTO import_audits
                (audit_id, provider, schema_version, snapshot_id, content_hash,
                 file_sha256, source_file, archived_file, generated_at, imported_at,
                 dataset_id, import_status, warning_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'pending', ?)
                """,
                [
                    audit_id, record["provider"], record["schema_version"],
                    record["snapshot_id"], record["content_hash"], record["file_sha256"],
                    record["source_file"], record.get("archived_file"),
                    record.get("generated_at"), _now(), record.get("warning_summary", ""),
                ],
            )
            return audit_id

    def finish_import_audit(
        self,
        audit_id: int,
        status: str,
        *,
        dataset_id: int | None = None,
        warning_summary: str = "",
    ) -> None:
        if status not in {"success", "rolled_back"}:
            raise ValueError(f"非法导入审计状态：{status}")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE import_audits
                SET import_status=?, dataset_id=?, imported_at=?, warning_summary=?
                WHERE audit_id=?
                """,
                [status, dataset_id, _now(), warning_summary, audit_id],
            )

    def list_dataset_series_ids(self, dataset_id: int) -> list[int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT series_id FROM series WHERE source_dataset_id=? ORDER BY series_id",
                [dataset_id],
            ).fetchall()
        return [int(row[0]) for row in rows]

    def get_indicator_history(self, indicator_codes: list[str]) -> pd.DataFrame:
        """供只读预览比较历史快照，不在 UI 中散落 SQL。"""
        if not indicator_codes:
            return pd.DataFrame(
                columns=["indicator_code", "date", "value", "dataset_id", "snapshot_id"]
            )
        placeholders = ",".join(["?"] * len(indicator_codes))
        with self._conn() as conn:
            return conn.execute(
                f"""
                SELECT i.code AS indicator_code, o.date, o.value,
                       s.source_dataset_id AS dataset_id, a.snapshot_id
                FROM observations o
                JOIN series s ON s.series_id=o.series_id
                JOIN indicators i ON i.indicator_id=s.indicator_id
                LEFT JOIN import_audits a
                  ON a.dataset_id=s.source_dataset_id AND a.import_status='success'
                WHERE i.code IN ({placeholders})
                ORDER BY s.source_dataset_id DESC, i.code, o.date
                """,
                indicator_codes,
            ).fetchdf()

    def get_analysis_snapshot(self, dataset_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT snapshot_id, generated_at, analysis_json, created_at "
                "FROM analysis_snapshots WHERE dataset_id=?",
                [dataset_id],
            ).fetchone()
        if row is None:
            return None
        return {
            "snapshot_id": row[0],
            "generated_at": row[1],
            "analysis": _loads(row[2], {}),
            "created_at": str(row[3] or ""),
        }

    def dataset_impact(self, dataset_id: int) -> dict[str, int]:
        """返回删除数据集时可能受影响的对象数量。"""
        with self._conn() as conn:
            series_rows = conn.execute(
                "SELECT series_id FROM series WHERE source_dataset_id = ?", [dataset_id]
            ).fetchall()
            series_ids = {int(row[0]) for row in series_rows}
            if not series_ids:
                return {"series": 0, "observations": 0, "steps": 0, "charts": 0}

            placeholders = ",".join(["?"] * len(series_ids))
            observation_count = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM observations "
                    f"WHERE series_id IN ({placeholders})",
                    list(series_ids),
                ).fetchone()[0]
            )
            step_count = sum(
                1
                for input_json, output_json in conn.execute(
                    "SELECT input_series, output_series FROM transform_steps"
                ).fetchall()
                if series_ids
                & (set(_loads(input_json, [])) | set(_loads(output_json, [])))
            )
            chart_count = sum(
                1
                for (config_json,) in conn.execute("SELECT config FROM charts").fetchall()
                if series_ids & set(_loads(config_json, {}).get("series_ids", []))
            )
            return {
                "series": len(series_ids),
                "observations": observation_count,
                "steps": step_count,
                "charts": chart_count,
            }

    def delete_dataset(self, dataset_id: int, delete_series: bool = False) -> dict[str, int]:
        """删除数据集；可选择同时清理其关联序列及依赖配置。"""
        impact = self.dataset_impact(dataset_id)
        with self._conn() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                series_rows = conn.execute(
                    "SELECT series_id, indicator_id FROM series "
                    "WHERE source_dataset_id = ?",
                    [dataset_id],
                ).fetchall()
                series_ids = {int(row[0]) for row in series_rows}
                indicator_ids = {int(row[1]) for row in series_rows}

                if delete_series and series_ids:
                    step_ids = [
                        int(step_id)
                        for step_id, input_json, output_json in conn.execute(
                            "SELECT step_id, input_series, output_series FROM transform_steps"
                        ).fetchall()
                        if series_ids
                        & (set(_loads(input_json, [])) | set(_loads(output_json, [])))
                    ]
                    chart_ids = [
                        int(chart_id)
                        for chart_id, config_json in conn.execute(
                            "SELECT chart_id, config FROM charts"
                        ).fetchall()
                        if series_ids & set(_loads(config_json, {}).get("series_ids", []))
                    ]

                    for chart_id in chart_ids:
                        conn.execute(
                            "DELETE FROM project_charts WHERE chart_id = ?", [chart_id]
                        )
                        conn.execute("DELETE FROM charts WHERE chart_id = ?", [chart_id])
                    for step_id in step_ids:
                        conn.execute(
                            "DELETE FROM transform_steps WHERE step_id = ?", [step_id]
                        )
                    for series_id in series_ids:
                        conn.execute(
                            "DELETE FROM observations WHERE series_id = ?", [series_id]
                        )
                        conn.execute("DELETE FROM series WHERE series_id = ?", [series_id])
                    for indicator_id in indicator_ids:
                        still_used = conn.execute(
                            "SELECT COUNT(*) FROM series WHERE indicator_id = ?",
                            [indicator_id],
                        ).fetchone()[0]
                        if not still_used:
                            conn.execute(
                                "DELETE FROM indicators WHERE indicator_id = ?",
                                [indicator_id],
                            )
                elif series_ids:
                    conn.execute(
                        "UPDATE series SET source_dataset_id = NULL "
                        "WHERE source_dataset_id = ?",
                        [dataset_id],
                    )

                conn.execute(
                    "DELETE FROM project_datasets WHERE dataset_id = ?", [dataset_id]
                )
                conn.execute(
                    "DELETE FROM field_mappings WHERE dataset_id = ?", [dataset_id]
                )
                conn.execute("DELETE FROM datasets WHERE dataset_id = ?", [dataset_id])
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return impact

    @staticmethod
    def _row_to_dataset(r: dict) -> DatasetMeta:
        return DatasetMeta(
            dataset_id=int(r["dataset_id"]),
            name=r["name"] or "",
            source_filename=r["source_filename"] or "",
            source_format=r["source_format"] or "",
            import_params=_loads(r["import_params"], {}),
            row_count=int(r["row_count"] or 0),
            column_count=int(r["column_count"] or 0),
            created_at=str(r["created_at"] or ""),
            raw_path=r["raw_path"] or "",
        )

    # ------------------------------------------------------------------ 字段映射
    def save_field_mappings(self, dataset_id: int, mappings: list[FieldMapping]) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM field_mappings WHERE dataset_id = ?", [dataset_id]
            )
            for m in mappings:
                conn.execute(
                    "INSERT INTO field_mappings (dataset_id, column_name, role) VALUES (?, ?, ?)",
                    [dataset_id, m.column, m.role],
                )

    def get_field_mappings(self, dataset_id: int) -> list[FieldMapping]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM field_mappings WHERE dataset_id = ? ORDER BY column_name",
                [dataset_id],
            ).fetchdf()
        return [FieldMapping(column=r["column_name"], role=r["role"]) for r in df.to_dict("records")]

    # ------------------------------------------------------------------ 指标
    def create_indicator(self, meta: IndicatorMeta) -> int:
        with self._conn() as conn:
            iid = self._next_id(conn, "indicators", "indicator_id")
            conn.execute(
                """
                INSERT INTO indicators
                (indicator_id, name, code, definition, unit, frequency, region,
                 currency, source_org, source_link, updated_at, nominal_or_real,
                 stock_or_flow, period_or_cumulative, seasonally_adjusted,
                 base_period, scope_note, user_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    iid,
                    meta.name,
                    meta.code,
                    meta.definition,
                    meta.unit,
                    meta.frequency,
                    meta.region,
                    meta.currency,
                    meta.source_org,
                    meta.source_link,
                    meta.updated_at,
                    meta.nominal_or_real,
                    meta.stock_or_flow,
                    meta.period_or_cumulative,
                    meta.seasonally_adjusted,
                    meta.base_period,
                    meta.scope_note,
                    meta.user_note,
                ],
            )
            return iid

    def update_indicator(self, meta: IndicatorMeta) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE indicators SET
                    name=?, code=?, definition=?, unit=?, frequency=?, region=?,
                    currency=?, source_org=?, source_link=?, updated_at=?,
                    nominal_or_real=?, stock_or_flow=?, period_or_cumulative=?,
                    seasonally_adjusted=?, base_period=?, scope_note=?, user_note=?
                WHERE indicator_id=?
                """,
                [
                    meta.name,
                    meta.code,
                    meta.definition,
                    meta.unit,
                    meta.frequency,
                    meta.region,
                    meta.currency,
                    meta.source_org,
                    meta.source_link,
                    meta.updated_at,
                    meta.nominal_or_real,
                    meta.stock_or_flow,
                    meta.period_or_cumulative,
                    meta.seasonally_adjusted,
                    meta.base_period,
                    meta.scope_note,
                    meta.user_note,
                    meta.indicator_id,
                ],
            )

    def get_indicator(self, indicator_id: int) -> IndicatorMeta | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM indicators WHERE indicator_id = ?", [indicator_id]
            ).fetchdf()
        if df.empty:
            return None
        return self._row_to_indicator(df.to_dict("records")[0])

    def list_indicators(self) -> list[IndicatorMeta]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM indicators ORDER BY name"
            ).fetchdf()
        return [self._row_to_indicator(r) for r in df.to_dict("records")]

    @staticmethod
    def _row_to_indicator(r: dict) -> IndicatorMeta:
        return IndicatorMeta(
            indicator_id=int(r["indicator_id"]),
            name=r["name"] or "",
            code=r["code"] or "",
            definition=r["definition"] or "",
            unit=r["unit"] or "",
            frequency=r["frequency"] or "",
            region=r["region"] or "",
            currency=r["currency"] or "",
            source_org=r["source_org"] or "",
            source_link=r["source_link"] or "",
            updated_at=r["updated_at"] or "",
            nominal_or_real=r["nominal_or_real"] or "unknown",
            stock_or_flow=r["stock_or_flow"] or "unknown",
            period_or_cumulative=r["period_or_cumulative"] or "unknown",
            seasonally_adjusted=r["seasonally_adjusted"] or "unknown",
            base_period=r["base_period"] or "",
            scope_note=r["scope_note"] or "",
            user_note=r["user_note"] or "",
        )

    # ------------------------------------------------------------------ 序列
    def create_series(
        self,
        indicator_id: int,
        entity: str = "",
        unit: str = "",
        frequency: str = "",
        currency: str = "",
        is_derived: bool = False,
        source_dataset_id: int | None = None,
    ) -> int:
        with self._conn() as conn:
            sid = self._next_id(conn, "series", "series_id")
            conn.execute(
                """
                INSERT INTO series
                (series_id, indicator_id, entity, unit, frequency, currency,
                 is_derived, source_dataset_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [sid, indicator_id, entity, unit, frequency, currency,
                 is_derived, source_dataset_id, _now()],
            )
            return sid

    def get_series(self, series_id: int) -> dict | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM series WHERE series_id = ?", [series_id]
            ).fetchdf()
        if df.empty:
            return None
        r = df.to_dict("records")[0]
        r["is_derived"] = bool(r["is_derived"])
        return r

    def list_series(self) -> list[dict]:
        with self._conn() as conn:
            df = conn.execute(
                """
                SELECT s.*, i.name AS indicator_name, i.code AS indicator_code
                FROM series s LEFT JOIN indicators i ON s.indicator_id = i.indicator_id
                ORDER BY s.series_id
                """
            ).fetchdf()
        out = []
        for r in df.to_dict("records"):
            r["is_derived"] = bool(r["is_derived"])
            out.append(r)
        return out

    def delete_series(self, series_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM observations WHERE series_id = ?", [series_id])
            conn.execute("DELETE FROM series WHERE series_id = ?", [series_id])

    # ------------------------------------------------------------------ 观测值
    def insert_observations(self, series_id: int, df: pd.DataFrame) -> int:
        """写入观测值。df 需含 date、value 两列。返回写入行数。"""
        if df.empty:
            return 0
        rows = [
            (series_id, _to_date(r["date"]), float(r["value"]))
            for r in df.to_dict("records")
            if pd.notna(r["value"])
        ]
        if not rows:
            return 0
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO observations (series_id, date, value) VALUES (?, ?, ?)",
                rows,
            )
        return len(rows)

    def get_observations(self, series_id: int) -> pd.DataFrame:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT date, value FROM observations WHERE series_id = ? ORDER BY date",
                [series_id],
            ).fetchdf()
        return df

    def get_many_observations(self, series_ids: list[int]) -> pd.DataFrame:
        """返回长表 DataFrame：series_id, date, value。"""
        if not series_ids:
            return pd.DataFrame(columns=["series_id", "date", "value"])
        placeholders = ",".join(["?"] * len(series_ids))
        with self._conn() as conn:
            df = conn.execute(
                f"SELECT series_id, date, value FROM observations "
                f"WHERE series_id IN ({placeholders}) ORDER BY series_id, date",
                series_ids,
            ).fetchdf()
        return df

    # ------------------------------------------------------------------ 变换
    def create_step(self, step: TransformStep) -> int:
        with self._conn() as conn:
            sid = self._next_id(conn, "transform_steps", "step_id")
            conn.execute(
                """
                INSERT INTO transform_steps
                (step_id, op_type, params, formula, description,
                 input_series, output_series, seq, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    sid,
                    step.op_type,
                    _dumps(step.params),
                    step.formula,
                    step.description,
                    _dumps(step.input_series),
                    _dumps(step.output_series),
                    step.seq,
                    _now(),
                ],
            )
            return sid

    def list_steps(self) -> list[TransformStep]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM transform_steps ORDER BY seq, step_id"
            ).fetchdf()
        return [self._row_to_step(r) for r in df.to_dict("records")]

    def get_step(self, step_id: int) -> TransformStep | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM transform_steps WHERE step_id = ?", [step_id]
            ).fetchdf()
        if df.empty:
            return None
        return self._row_to_step(df.to_dict("records")[0])

    def delete_step(self, step_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM transform_steps WHERE step_id = ?", [step_id])

    @staticmethod
    def _row_to_step(r: dict) -> TransformStep:
        return TransformStep(
            step_id=int(r["step_id"]),
            op_type=r["op_type"] or "",
            params=_loads(r["params"], {}),
            formula=r["formula"] or "",
            description=r["description"] or "",
            input_series=_loads(r["input_series"], []),
            output_series=_loads(r["output_series"], []),
            seq=int(r["seq"] or 0),
            created_at=str(r["created_at"] or ""),
        )

    # ------------------------------------------------------------------ 图表
    def save_chart(self, spec: ChartSpec) -> int:
        with self._conn() as conn:
            if spec.chart_id is None:
                cid = self._next_id(conn, "charts", "chart_id")
                conn.execute(
                    "INSERT INTO charts (chart_id, name, chart_type, config, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [cid, spec.name, spec.chart_type, _dumps(spec.model_dump()),
                     _now(), _now()],
                )
                return cid
            conn.execute(
                "UPDATE charts SET name=?, chart_type=?, config=?, updated_at=? WHERE chart_id=?",
                [spec.name, spec.chart_type, _dumps(spec.model_dump()), _now(), spec.chart_id],
            )
            return spec.chart_id

    def get_chart(self, chart_id: int) -> ChartSpec | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM charts WHERE chart_id = ?", [chart_id]
            ).fetchdf()
        if df.empty:
            return None
        r = df.to_dict("records")[0]
        cfg = _loads(r["config"], {})
        cfg["chart_id"] = int(r["chart_id"])
        return ChartSpec(**cfg)

    def list_charts(self) -> list[ChartSpec]:
        with self._conn() as conn:
            df = conn.execute("SELECT * FROM charts ORDER BY updated_at DESC").fetchdf()
        out = []
        for r in df.to_dict("records"):
            cfg = _loads(r["config"], {})
            cfg["chart_id"] = int(r["chart_id"])
            out.append(ChartSpec(**cfg))
        return out

    def delete_chart(self, chart_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM project_charts WHERE chart_id = ?", [chart_id])
            conn.execute("DELETE FROM charts WHERE chart_id = ?", [chart_id])

    # ------------------------------------------------------------------ 项目
    def create_project(self, name: str, research_question: str = "") -> int:
        with self._conn() as conn:
            pid = self._next_id(conn, "projects", "project_id")
            conn.execute(
                "INSERT INTO projects (project_id, name, research_question, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [pid, name, research_question, _now(), _now()],
            )
            return pid

    def update_project(
        self,
        project_id: int,
        name: str,
        research_question: str = "",
        notes: str = "",
        data_limitations: str = "",
        sources: str = "",
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE projects SET name=?, research_question=?, notes=?, "
                "data_limitations=?, sources=?, updated_at=? WHERE project_id=?",
                [name, research_question, notes, data_limitations, sources,
                 _now(), project_id],
            )

    def get_project(self, project_id: int) -> dict | None:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?", [project_id]
            ).fetchdf()
        if df.empty:
            return None
        r = df.to_dict("records")[0]
        r["project_id"] = int(r["project_id"])
        return r

    def list_projects(self) -> list[dict]:
        with self._conn() as conn:
            df = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchdf()
        out = []
        for r in df.to_dict("records"):
            r["project_id"] = int(r["project_id"])
            out.append(r)
        return out

    def delete_project(self, project_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM project_entries WHERE project_id = ?", [project_id])
            conn.execute("DELETE FROM project_datasets WHERE project_id = ?", [project_id])
            conn.execute("DELETE FROM project_charts WHERE project_id = ?", [project_id])
            conn.execute("DELETE FROM projects WHERE project_id = ?", [project_id])

    def add_project_entry(self, project_id: int, kind: str, content: str) -> int:
        with self._conn() as conn:
            eid = self._next_id(conn, "project_entries", "entry_id")
            conn.execute(
                "INSERT INTO project_entries (entry_id, project_id, kind, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [eid, project_id, kind, content, _now()],
            )
            return eid

    def list_project_entries(self, project_id: int) -> list[dict]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT * FROM project_entries WHERE project_id = ? ORDER BY entry_id",
                [project_id],
            ).fetchdf()
        out = []
        for r in df.to_dict("records"):
            r["entry_id"] = int(r["entry_id"])
            out.append(r)
        return out

    def delete_project_entry(self, entry_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM project_entries WHERE entry_id = ?", [entry_id])

    def link_project_dataset(self, project_id: int, dataset_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO project_datasets VALUES (?, ?)",
                [project_id, dataset_id],
            )

    def link_project_chart(self, project_id: int, chart_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO project_charts VALUES (?, ?)",
                [project_id, chart_id],
            )

    def list_project_datasets(self, project_id: int) -> list[int]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT dataset_id FROM project_datasets WHERE project_id = ? ORDER BY dataset_id",
                [project_id],
            ).fetchdf()
        return [int(x) for x in df["dataset_id"].tolist()]

    def list_project_charts(self, project_id: int) -> list[int]:
        with self._conn() as conn:
            df = conn.execute(
                "SELECT chart_id FROM project_charts WHERE project_id = ? ORDER BY chart_id",
                [project_id],
            ).fetchdf()
        return [int(x) for x in df["chart_id"].tolist()]

    # ------------------------------------------------------------------ 备份/恢复
    def backup(self, target: str | Path) -> str:
        target = Path(target)
        if target.suffix != ".duckdb":
            target = target.with_suffix(".duckdb")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            target = target.with_name(f"{target.stem}_{stamp}{target.suffix}")
        shutil.copy2(self.db_path, target)
        return str(target)

    def validate_backup(self, source: str | Path) -> dict[str, int]:
        """验证备份文件可打开、结构完整且版本不高于当前程序。"""
        source = Path(source)
        if source.suffix.lower() != ".duckdb":
            raise ValueError("恢复文件必须是 .duckdb 格式")
        if not source.is_file():
            raise ValueError("恢复文件不存在")
        if source.resolve() == Path(self.db_path).resolve():
            raise ValueError("不能用当前正在使用的数据库恢复自身")

        try:
            with duckdb.connect(str(source), read_only=True) as conn:
                tables = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'main'"
                    ).fetchall()
                }
                missing = sorted(_REQUIRED_TABLES - tables)
                if missing:
                    raise ValueError(f"备份缺少必要数据表：{', '.join(missing)}")
                version_row = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_version"
                ).fetchone()
                version = int(version_row[0]) if version_row else 0
                if version > SCHEMA_VERSION:
                    raise ValueError(
                        f"备份版本 {version} 高于当前程序支持的 {SCHEMA_VERSION}"
                    )
                return {"schema_version": version, "table_count": len(tables)}
        except ValueError:
            raise
        except duckdb.Error as exc:
            raise ValueError(f"无法读取 DuckDB 备份：{exc}") from exc

    def restore(self, source: str | Path, backup_dir: str | Path | None = None) -> str:
        """校验后原子恢复数据库；失败时自动回滚到恢复前备份。"""
        source = Path(source)
        self.validate_backup(source)
        db_path = Path(self.db_path)
        backup_root = Path(backup_dir) if backup_dir is not None else db_path.parent
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        pre_restore = Path(self.backup(backup_root / f"pre_restore_{stamp}.duckdb"))
        temp_path = db_path.with_name(f".{db_path.name}.{uuid4().hex}.restore.tmp")
        replaced = False
        try:
            shutil.copy2(source, temp_path)
            os.replace(temp_path, db_path)
            replaced = True
            self.migrate()
        except Exception:
            if replaced:
                rollback_temp = db_path.with_name(
                    f".{db_path.name}.{uuid4().hex}.rollback.tmp"
                )
                shutil.copy2(pre_restore, rollback_temp)
                os.replace(rollback_temp, db_path)
            raise
        finally:
            temp_path.unlink(missing_ok=True)
        return str(pre_restore)


def _to_date(value):
    """把任意可解析的日期值归一化为 datetime.date。"""
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return pd.to_datetime(value).date()
    return value
