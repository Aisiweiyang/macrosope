"""变换管道测试：apply / undo / rerun。"""
from __future__ import annotations

import pandas as pd
import pytest
from macrosope.models import IndicatorMeta
from macrosope.transforms import Pipeline


def _add_series(repo, name, values, freq="monthly", unit=""):
    ind = IndicatorMeta(name=name, unit=unit, frequency=freq)
    iid = repo.create_indicator(ind)
    sid = repo.create_series(indicator_id=iid, unit=unit, frequency=freq)
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=len(values), freq="MS"),
        "value": values,
    })
    repo.insert_observations(sid, df)
    return sid


def test_apply_undo_rerun(repo):
    sid = _add_series(repo, "GDP", list(range(100, 124)))
    pipe = Pipeline(repo)

    out_ids = pipe.apply("yoy", [sid], {"freq": "monthly"})
    assert len(out_ids) == 1
    out = repo.get_observations(out_ids[0])
    # 24 期数据的前 12 期同比不可计算，观测只存可计算的值
    assert len(out) == 12
    assert out["value"].iloc[0] == pytest.approx(12.0)  # (112/100-1)*100

    # 步骤已记录
    steps = repo.list_steps()
    assert len(steps) == 1
    step_id = steps[0].step_id

    # 撤销
    pipe.undo(step_id)
    assert repo.get_series(out_ids[0]) is None
    assert repo.list_steps() == []


def test_two_input_per_capita(repo):
    gdp = _add_series(repo, "GDP", [100.0, 100.0, 100.0])
    pop = _add_series(repo, "人口", [100.0, 200.0, 400.0])
    pipe = Pipeline(repo)
    out_ids = pipe.apply("per_capita", [gdp, pop], {})
    out = repo.get_observations(out_ids[0])
    assert out["value"].iloc[0] == pytest.approx(1.0)
    assert out["value"].iloc[2] == pytest.approx(0.25)


def test_resample_rejects_upsampling(repo):
    sid = _add_series(repo, "M", [1.0] * 12, freq="monthly")
    pipe = Pipeline(repo)
    with pytest.raises(ValueError):
        pipe.apply("resample", [sid], {"to_freq": "daily", "method": "sum"})


def test_unknown_op_raises(repo):
    pipe = Pipeline(repo)
    with pytest.raises(ValueError):
        pipe.apply("nonexistent_op", [1], {})
