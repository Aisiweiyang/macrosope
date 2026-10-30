"""DuckDB 仓储测试：保存/恢复、备份、序列与观测往返。"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest
from macrosope.models import (
    ChartSpec,
    DatasetMeta,
    FieldMapping,
    IndicatorMeta,
    TransformStep,
)


def test_create_and_get_series(repo):
    iid = repo.create_indicator(IndicatorMeta(name="GDP", unit="亿元", frequency="monthly"))
    sid = repo.create_series(indicator_id=iid, entity="中国", unit="亿元", frequency="monthly")
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=3, freq="MS"),
        "value": [1.0, 2.0, 3.0],
    })
    n = repo.insert_observations(sid, df)
    assert n == 3
    out = repo.get_observations(sid)
    assert out["value"].tolist() == [1.0, 2.0, 3.0]


def test_delete_series(repo):
    iid = repo.create_indicator(IndicatorMeta(name="X"))
    sid = repo.create_series(indicator_id=iid)
    repo.insert_observations(sid, pd.DataFrame({"date": ["2023-01-01"], "value": [1.0]}))
    repo.delete_series(sid)
    assert repo.get_series(sid) is None
    assert repo.get_observations(sid).empty


def test_backup_and_restore(repo, tmp_path):
    iid = repo.create_indicator(IndicatorMeta(name="GDP"))
    sid = repo.create_series(indicator_id=iid)
    repo.insert_observations(sid, pd.DataFrame({"date": ["2023-01-01"], "value": [1.0]}))

    backup_path = repo.backup(tmp_path / "backup.duckdb")

    # 清空后恢复
    repo.delete_series(sid)
    assert repo.list_series() == []
    pre_restore = repo.restore(backup_path)
    assert len(repo.list_series()) == 1
    assert Path(pre_restore).is_file()


def test_dataset_and_field_mapping(repo):
    did = repo.create_dataset(DatasetMeta(name="test", source_format="csv"))
    repo.save_field_mappings(did, [FieldMapping(column="日期", role="date")])
    assert repo.get_field_mappings(did)[0].role == "date"
    assert repo.get_dataset(did).name == "test"


def test_import_bundle_rolls_back_on_observation_conflict(repo):
    payload = {
        "indicator": IndicatorMeta(name="GDP"),
        "series": {"entity": "中国", "frequency": "monthly"},
        "observations": pd.DataFrame({
            "date": ["2023-01-01", "2023-01-01"],
            "value": [1.0, 2.0],
        }),
    }
    with pytest.raises(duckdb.ConstraintException):
        repo.import_dataset_bundle(
            DatasetMeta(name="冲突数据"),
            [FieldMapping(column="日期", role="date")],
            [payload],
        )
    assert repo.list_datasets() == []
    assert repo.list_indicators() == []
    assert repo.list_series() == []


def test_delete_dataset_can_preserve_series(repo):
    did = repo.create_dataset(DatasetMeta(name="保留序列"))
    iid = repo.create_indicator(IndicatorMeta(name="GDP"))
    sid = repo.create_series(iid, source_dataset_id=did)
    repo.insert_observations(
        sid, pd.DataFrame({"date": ["2023-01-01"], "value": [1.0]})
    )

    impact = repo.delete_dataset(did, delete_series=False)

    assert impact["series"] == 1
    assert repo.get_dataset(did) is None
    assert repo.get_series(sid) is not None
    assert pd.isna(repo.get_series(sid)["source_dataset_id"])
    assert not repo.get_observations(sid).empty


def test_delete_dataset_cascade_cleans_dependencies(repo):
    did = repo.create_dataset(DatasetMeta(name="级联删除"))
    iid = repo.create_indicator(IndicatorMeta(name="GDP"))
    sid = repo.create_series(iid, source_dataset_id=did)
    repo.insert_observations(
        sid, pd.DataFrame({"date": ["2023-01-01"], "value": [1.0]})
    )
    step_id = repo.create_step(TransformStep(input_series=[sid], output_series=[sid]))
    chart_id = repo.save_chart(ChartSpec(name="GDP", chart_type="line", series_ids=[sid]))
    project_id = repo.create_project("测试项目")
    repo.link_project_dataset(project_id, did)
    repo.link_project_chart(project_id, chart_id)

    impact = repo.delete_dataset(did, delete_series=True)

    assert impact == {"series": 1, "observations": 1, "steps": 1, "charts": 1}
    assert repo.get_dataset(did) is None
    assert repo.get_series(sid) is None
    assert repo.get_indicator(iid) is None
    assert repo.get_step(step_id) is None
    assert repo.get_chart(chart_id) is None
    assert repo.list_project_datasets(project_id) == []
    assert repo.list_project_charts(project_id) == []


def test_restore_rejects_invalid_database(repo, tmp_path):
    iid = repo.create_indicator(IndicatorMeta(name="应保留"))
    invalid = tmp_path / "invalid.duckdb"
    invalid.write_text("not a database", encoding="utf-8")

    with pytest.raises(ValueError, match="无法读取 DuckDB"):
        repo.restore(invalid)

    assert repo.get_indicator(iid).name == "应保留"


def test_backup_does_not_overwrite_existing_file(repo, tmp_path):
    requested = Path(repo.backup(tmp_path / "backup.duckdb"))
    second = Path(repo.backup(tmp_path / "backup.duckdb"))
    assert requested != second
    assert requested.is_file()
    assert second.is_file()


def test_project_entries_kinds(repo):
    pid = repo.create_project("通胀研究", "为什么CPI上涨")
    repo.add_project_entry(pid, "fact", "2024年CPI同比2.0%")
    repo.add_project_entry(pid, "hypothesis", "猪周期推动食品价格")
    entries = repo.list_project_entries(pid)
    assert {e["kind"] for e in entries} == {"fact", "hypothesis"}
