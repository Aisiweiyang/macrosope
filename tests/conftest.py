"""pytest 共享夹具。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# 确保 data/ 目录存在（pytest --basetemp=data/.pytest-tmp 的父目录）
from macrosope.config import ensure_dirs

ensure_dirs()


@pytest.fixture
def repo(tmp_path):
    from macrosope.db import Repository

    return Repository(tmp_path / "test.duckdb")


@pytest.fixture
def monthly_df() -> pd.DataFrame:
    """24 期月度序列，值 100..123，便于人工核验。"""
    dates = pd.date_range("2023-01-01", periods=24, freq="MS")
    values = np.arange(24, dtype=float) + 100.0
    return pd.DataFrame({"date": dates, "value": values})


@pytest.fixture
def quarterly_df() -> pd.DataFrame:
    """8 期季度序列。"""
    dates = pd.date_range("2023-01-01", periods=8, freq="QS")
    values = np.array([100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0])
    return pd.DataFrame({"date": dates, "value": values})
