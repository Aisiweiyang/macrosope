"""导入器测试：编码、分隔符、表头、Excel 多表、拒绝 XLSM、JSON/Parquet。"""
from __future__ import annotations

import pandas as pd
import pytest
from macrosope.importers import (
    list_sheets,
    normalize_dataframe,
    read_csv,
    read_excel,
    read_json,
    read_parquet,
)


def _write(tmp_path, name, text, encoding="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(encoding))
    return p


def test_read_csv_utf8(tmp_path):
    p = _write(tmp_path, "a.csv", "日期,GDP\n2023-01,100\n2023-02,101\n")
    r = read_csv(p)
    assert list(r.df.columns) == ["日期", "GDP"]
    assert len(r.df) == 2


def test_read_csv_gbk(tmp_path):
    p = _write(tmp_path, "a.csv", "日期,GDP\n2023-01,100\n", encoding="gbk")
    r = read_csv(p)
    assert list(r.df.columns) == ["日期", "GDP"]


def test_read_csv_semicolon_delimiter(tmp_path):
    p = _write(tmp_path, "a.csv", "日期;GDP\n2023-01;100\n")
    r = read_csv(p)
    assert r.settings["delimiter"] == ";"


def test_read_csv_header_and_skiprows(tmp_path):
    p = _write(tmp_path, "a.csv", "这是说明行\n第二行说明\n日期,GDP\n2023-01,100\n")
    r = read_csv(p, header_row=0, skiprows=2)
    assert list(r.df.columns) == ["日期", "GDP"]
    assert len(r.df) == 1


def test_normalize_percent_and_thousands():
    df = pd.DataFrame({"a": ["1,234.5", "56%", "3,000"]})
    out, _ = normalize_dataframe(df, thousands_sep=",", percent=True)
    assert out["a"].iloc[0] == pytest.approx(1234.5)
    assert out["a"].iloc[1] == pytest.approx(0.56)
    assert out["a"].iloc[2] == pytest.approx(3000.0)


def test_excel_multi_sheet(tmp_path):
    p = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        pd.DataFrame({"a": [1]}).to_excel(w, sheet_name="SheetA", index=False)
        pd.DataFrame({"b": [2]}).to_excel(w, sheet_name="SheetB", index=False)
    assert set(list_sheets(p)) == {"SheetA", "SheetB"}
    r = read_excel(p, sheet_name="SheetB")
    assert list(r.df.columns) == ["b"]


def test_excel_reject_xlsm(tmp_path):
    p = tmp_path / "macro.xlsm"
    p.write_bytes(b"fake")
    with pytest.raises(ValueError):
        read_excel(p)


def test_read_json(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('[{"日期":"2023-01","GDP":100},{"日期":"2023-02","GDP":101}]', encoding="utf-8")
    r = read_json(p, orient="records")
    assert len(r.df) == 2


def test_read_parquet(tmp_path):
    p = tmp_path / "a.parquet"
    pd.DataFrame({"日期": ["2023-01"], "GDP": [100.0]}).to_parquet(p)
    r = read_parquet(p)
    assert len(r.df) == 1
