"""端到端导入落库测试：宽表与长表 CSV。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from macrosope.models import IndicatorMeta
from macrosope.services import ingest


def _wide_csv(tmp_path):
    p = tmp_path / "wide.csv"
    p.write_text(
        "日期,GDP,CPI\n2023-01,100,2.0\n2023-02,101,2.1\n", encoding="utf-8"
    )
    return str(p)


def _long_csv(tmp_path):
    p = tmp_path / "long.csv"
    p.write_text(
        "日期,指标,数值,单位\n2023-01,GDP,100,亿元\n2023-02,GDP,101,亿元\n"
        "2023-01,CPI,2.0,%\n2023-02,CPI,2.1,%\n",
        encoding="utf-8",
    )
    return str(p)


def test_ingest_wide(repo, tmp_path):
    p = _wide_csv(tmp_path)
    roles = {"日期": "date", "GDP": "value", "CPI": "value"}
    template = IndicatorMeta(unit="亿元", frequency="monthly", region="中国")
    did, sids = ingest(
        repo, p, "csv", {"encoding": "utf-8", "delimiter": ",", "header_row": 0, "skiprows": 0},
        roles, template,
    )
    assert len(sids) == 2  # GDP、CPI 两条序列
    assert repo.get_dataset(did) is not None
    assert all(repo.get_series(sid)["source_dataset_id"] == did for sid in sids)
    assert {m.column: m.role for m in repo.get_field_mappings(did)} == roles
    raw_path = Path(repo.get_dataset(did).raw_path)
    assert raw_path.is_file()
    assert raw_path.parent == Path(repo.db_path).parent / "raw"


def test_ingest_long(repo, tmp_path):
    p = _long_csv(tmp_path)
    roles = {"日期": "date", "指标": "indicator", "数值": "value", "单位": "unit"}
    template = IndicatorMeta(frequency="monthly", region="中国")
    did, sids = ingest(
        repo, p, "csv", {"encoding": "utf-8", "delimiter": ",", "header_row": 0, "skiprows": 0},
        roles, template,
    )
    assert len(sids) == 2
    # GDP 单位取自「单位」列
    names = {repo.get_indicator(repo.get_series(s)["indicator_id"]).name for s in sids}
    assert names == {"GDP", "CPI"}


def test_ingest_bad_date_raises(repo, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("日期,GDP\n2023-13,100\n", encoding="utf-8")
    roles = {"日期": "date", "GDP": "value"}
    template = IndicatorMeta()
    with pytest.raises(ValueError):
        ingest(
            repo, str(p), "csv",
            {"encoding": "utf-8", "delimiter": ",", "header_row": 0, "skiprows": 0},
            roles, template,
        )


def test_ingest_duplicate_dates_are_rejected(repo, tmp_path):
    p = tmp_path / "duplicate.csv"
    p.write_text("日期,GDP\n2023-01,100\n2023-01,101\n", encoding="utf-8")
    roles = {"日期": "date", "GDP": "value"}
    with pytest.raises(ValueError, match="重复日期"):
        ingest(
            repo,
            str(p),
            "csv",
            {"encoding": "utf-8", "delimiter": ",", "header_row": 0, "skiprows": 0},
            roles,
            IndicatorMeta(),
        )
    assert repo.list_datasets() == []
    assert repo.list_series() == []


def test_raw_archives_never_overwrite(repo, tmp_path):
    p = _wide_csv(tmp_path)
    roles = {"日期": "date", "GDP": "value", "CPI": "value"}
    params = {"encoding": "utf-8", "delimiter": ",", "header_row": 0, "skiprows": 0}
    first_id, _ = ingest(repo, p, "csv", params, roles, IndicatorMeta())
    second_id, _ = ingest(repo, p, "csv", params, roles, IndicatorMeta())
    first_path = Path(repo.get_dataset(first_id).raw_path)
    second_path = Path(repo.get_dataset(second_id).raw_path)
    assert first_path != second_path
    assert first_path.read_bytes() == second_path.read_bytes()


def test_database_failure_removes_new_archive(repo, tmp_path, monkeypatch):
    p = _wide_csv(tmp_path)
    roles = {"日期": "date", "GDP": "value", "CPI": "value"}

    def fail_import(*_args, **_kwargs):
        raise RuntimeError("模拟数据库失败")

    monkeypatch.setattr(repo, "import_dataset_bundle", fail_import)
    with pytest.raises(RuntimeError, match="模拟数据库失败"):
        ingest(
            repo,
            p,
            "csv",
            {"encoding": "utf-8", "delimiter": ",", "header_row": 0, "skiprows": 0},
            roles,
            IndicatorMeta(),
        )
    raw_dir = Path(repo.db_path).parent / "raw"
    assert not raw_dir.exists() or list(raw_dir.iterdir()) == []


@pytest.mark.parametrize("date_format", [None, "%Y"])
def test_json_integer_years_are_calendar_years(repo, tmp_path, date_format):
    path = tmp_path / "annual.json"
    path.write_text('[{"year":2015,"population":100},{"year":2016,"population":101}]',
                    encoding="utf-8")
    _, sids = ingest(
        repo, str(path), "json", {"orient": "records"},
        {"year": "date", "population": "value"},
        IndicatorMeta(frequency="annual"), date_format=date_format,
    )
    dates = pd.to_datetime(repo.get_observations(sids[0])["date"])
    assert dates.dt.strftime("%Y-%m-%d").tolist() == ["2015-01-01", "2016-01-01"]


def test_integer_compact_dates_are_not_epoch_timestamps(repo, tmp_path):
    path = tmp_path / "daily.json"
    path.write_text('[{"date":20230101,"value":1},{"date":20230102,"value":2}]',
                    encoding="utf-8")
    _, sids = ingest(
        repo, str(path), "json", {"orient": "records"},
        {"date": "date", "value": "value"}, IndicatorMeta(frequency="daily"),
    )
    dates = pd.to_datetime(repo.get_observations(sids[0])["date"])
    assert dates.dt.strftime("%Y-%m-%d").tolist() == ["2023-01-01", "2023-01-02"]
